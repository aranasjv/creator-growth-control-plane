using System.Globalization;
using System.Text.Json;
using CreatorGrowthControlPlane.Orchestrator.Contracts;
using CreatorGrowthControlPlane.Orchestrator.Data;
using CreatorGrowthControlPlane.Orchestrator.Domain;
using Microsoft.EntityFrameworkCore;

namespace CreatorGrowthControlPlane.Orchestrator.Services;

public sealed class LegacyCacheSyncService(CreatorGrowthControlPlaneDbContext dbContext, IWebHostEnvironment environment)
{
    public async Task<SyncLegacyCacheResponse> SyncAsync(CancellationToken cancellationToken = default)
    {
        var repositoryRoot = ResolveRepositoryRoot();
        var cacheRoot = Path.Combine(repositoryRoot, ".mp");

        var accountsImported = 0;
        var assetsImported = 0;
        var productsImported = 0;

        if (Directory.Exists(cacheRoot))
        {
            (accountsImported, assetsImported) = await SyncAccountsAsync(cacheRoot, cancellationToken);
            productsImported = await SyncProductsAsync(cacheRoot, cancellationToken);
        }

        await dbContext.SaveChangesAsync(cancellationToken);
        return new SyncLegacyCacheResponse(accountsImported, assetsImported, productsImported);
    }

    private string ResolveRepositoryRoot()
    {
        var configuredRoot = Environment.GetEnvironmentVariable("CGCP_REPOSITORY_ROOT");
        if (!string.IsNullOrWhiteSpace(configuredRoot) && Directory.Exists(configuredRoot))
        {
            return configuredRoot;
        }

        var candidates = new[]
        {
            environment.ContentRootPath,
            Path.GetFullPath(Path.Combine(environment.ContentRootPath, "..", "..")),
            Path.GetFullPath(Path.Combine(environment.ContentRootPath, "..", "..", ".."))
        };

        foreach (var candidate in candidates.Distinct())
        {
            if (File.Exists(Path.Combine(candidate, "config.example.json")) || Directory.Exists(Path.Combine(candidate, ".mp")))
            {
                return candidate;
            }
        }

        return environment.ContentRootPath;
    }

    private async Task<(int accountsImported, int assetsImported)> SyncAccountsAsync(string cacheRoot, CancellationToken cancellationToken)
    {
        var accountsImported = 0;
        var assetsImported = 0;

        var twitterSync = await SyncProviderAsync(
            Path.Combine(cacheRoot, "twitter.json"),
            "twitter",
            accountElement => accountElement.TryGetProperty("topic", out var value) ? value.GetString() : null,
            _ => null,
            _ => null,
            accountElement => accountElement.TryGetProperty("posts", out var value) ? value : default,
            (accountId, item) => new ContentAssetEntity
            {
                Id = Guid.NewGuid(),
                Kind = "twitter_post",
                Provider = "twitter",
                SourceId = $"twitter:{accountId}:{item.GetProperty("date").GetString()}:{item.GetProperty("content").GetString()}".ToLowerInvariant(),
                AccountId = accountId,
                Title = Trim(item.GetProperty("content").GetString(), 72),
                Description = item.GetProperty("content").GetString(),
                PublishedAt = ParseDate(item.GetProperty("date").GetString(), "MM/dd/yyyy, HH:mm:ss")
            },
            cancellationToken);

        accountsImported += twitterSync.accountsImported;
        assetsImported += twitterSync.assetsImported;

        var youtubeSync = await SyncProviderAsync(
            Path.Combine(cacheRoot, "youtube.json"),
            "youtube",
            _ => null,
            accountElement => accountElement.TryGetProperty("niche", out var value) ? value.GetString() : null,
            accountElement => accountElement.TryGetProperty("language", out var value) ? value.GetString() : null,
            accountElement => accountElement.TryGetProperty("videos", out var value) ? value : default,
            (accountId, item) => new ContentAssetEntity
            {
                Id = Guid.NewGuid(),
                Kind = "youtube_video",
                Provider = "youtube",
                SourceId = item.TryGetProperty("url", out var urlElement) && !string.IsNullOrWhiteSpace(urlElement.GetString())
                    ? urlElement.GetString()!.ToLowerInvariant()
                    : $"youtube:{accountId}:{item.GetProperty("date").GetString()}:{item.GetProperty("title").GetString()}".ToLowerInvariant(),
                AccountId = accountId,
                Title = item.GetProperty("title").GetString() ?? "Untitled video",
                Description = item.TryGetProperty("description", out var descriptionElement) ? descriptionElement.GetString() : null,
                Url = item.TryGetProperty("url", out var urlValue) ? urlValue.GetString() : null,
                PublishedAt = ParseDate(item.GetProperty("date").GetString(), "yyyy-MM-dd HH:mm:ss")
            },
            cancellationToken);

        accountsImported += youtubeSync.accountsImported;
        assetsImported += youtubeSync.assetsImported;

        return (accountsImported, assetsImported);
    }

    private async Task<int> SyncProductsAsync(string cacheRoot, CancellationToken cancellationToken)
    {
        var path = Path.Combine(cacheRoot, "afm.json");
        if (!File.Exists(path))
        {
            return 0;
        }

        using var document = JsonDocument.Parse(await File.ReadAllTextAsync(path, cancellationToken));
        if (!document.RootElement.TryGetProperty("products", out var productsElement) || productsElement.ValueKind != JsonValueKind.Array)
        {
            return 0;
        }

        var imported = 0;
        foreach (var productElement in productsElement.EnumerateArray())
        {
            var productId = productElement.TryGetProperty("id", out var idValue)
                ? idValue.GetString() ?? Guid.NewGuid().ToString("N")
                : Guid.NewGuid().ToString("N");

            var existing = await dbContext.AffiliateProducts.FindAsync([productId], cancellationToken);
            if (existing is null)
            {
                existing = new AffiliateProductEntity { Id = productId };
                dbContext.AffiliateProducts.Add(existing);
                imported++;
            }

            existing.AffiliateLink = productElement.TryGetProperty("affiliate_link", out var linkValue)
                ? linkValue.GetString() ?? string.Empty
                : string.Empty;
            existing.AccountId = productElement.TryGetProperty("twitter_uuid", out var accountValue)
                ? accountValue.GetString()
                : null;
            existing.AccountNickname = existing.AccountId is null
                ? null
                : await dbContext.Accounts.Where(account => account.Id == existing.AccountId).Select(account => account.Nickname).FirstOrDefaultAsync(cancellationToken);
            existing.CreatedAt = DateTimeOffset.UtcNow;
        }

        return imported;
    }

    private async Task<(int accountsImported, int assetsImported)> SyncProviderAsync(
        string path,
        string provider,
        Func<JsonElement, string?> topicFactory,
        Func<JsonElement, string?> nicheFactory,
        Func<JsonElement, string?> languageFactory,
        Func<JsonElement, JsonElement> itemsFactory,
        Func<string, JsonElement, ContentAssetEntity> assetFactory,
        CancellationToken cancellationToken)
    {
        if (!File.Exists(path))
        {
            return (0, 0);
        }

        using var document = JsonDocument.Parse(await File.ReadAllTextAsync(path, cancellationToken));
        if (!document.RootElement.TryGetProperty("accounts", out var accountsElement) || accountsElement.ValueKind != JsonValueKind.Array)
        {
            return (0, 0);
        }

        var importedAssets = 0;
        var importedAccounts = 0;

        foreach (var accountElement in accountsElement.EnumerateArray())
        {
            var accountId = accountElement.GetProperty("id").GetString() ?? Guid.NewGuid().ToString("N");
            var account = await dbContext.Accounts.Include(item => item.Assets).FirstOrDefaultAsync(item => item.Id == accountId, cancellationToken);

            if (account is null)
            {
                account = new AccountEntity { Id = accountId, Provider = provider };
                dbContext.Accounts.Add(account);
                importedAccounts++;
            }

            account.Provider = provider;
            account.Nickname = accountElement.TryGetProperty("nickname", out var nicknameValue)
                ? nicknameValue.GetString() ?? provider
                : provider;
            account.Topic = topicFactory(accountElement);
            account.Niche = nicheFactory(accountElement);
            account.Language = languageFactory(accountElement);

            var itemsElement = itemsFactory(accountElement);
            if (itemsElement.ValueKind != JsonValueKind.Array)
            {
                continue;
            }

            foreach (var item in itemsElement.EnumerateArray())
            {
                var asset = assetFactory(accountId, item);
                var exists = await dbContext.ContentAssets.AnyAsync(existing => existing.SourceId == asset.SourceId, cancellationToken);
                if (exists)
                {
                    continue;
                }

                dbContext.ContentAssets.Add(asset);
                importedAssets++;

                if (account.LastActiveAt is null || asset.PublishedAt > account.LastActiveAt)
                {
                    account.LastActiveAt = asset.PublishedAt;
                }
            }
        }

        return (importedAccounts, importedAssets);
    }

    private static string Trim(string? value, int length)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "Untitled";
        }

        return value.Length <= length ? value : value[..length].TrimEnd() + "...";
    }

    private static DateTimeOffset ParseDate(string? value, string format)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return DateTimeOffset.UtcNow;
        }

        return DateTimeOffset.TryParseExact(value, format, CultureInfo.InvariantCulture, DateTimeStyles.AssumeLocal, out var parsed)
            ? parsed
            : DateTimeOffset.TryParse(value, out parsed)
                ? parsed
                : DateTimeOffset.UtcNow;
    }
}

