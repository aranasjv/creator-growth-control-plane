using System.Text.Json.Nodes;
using System.Text;
using System.Text.Json;
using CreatorGrowthControlPlane.Orchestrator.Data;
using Microsoft.EntityFrameworkCore;

namespace CreatorGrowthControlPlane.Orchestrator.Endpoints;

public static class DashboardEndpoints
{
    public static IEndpointRouteBuilder MapDashboardEndpoints(this IEndpointRouteBuilder app)
    {
        var dashboard = app.MapGroup("/api");
        dashboard.MapGet("/overview", GetOverviewAsync);
        dashboard.MapGet("/accounts", GetAccountsAsync);
        dashboard.MapPut("/accounts/{accountId}", UpdateAccountAsync);
        dashboard.MapGet("/content", GetContentAsync);
        dashboard.MapGet("/affiliate/overview", GetAffiliateOverviewAsync);
        dashboard.MapGet("/profit", GetProfitAsync);
        dashboard.MapGet("/outreach/leads", GetOutreachLeadsAsync);
        return app;
    }

    private static async Task<IResult> GetOverviewAsync(CreatorGrowthControlPlaneDbContext dbContext, CancellationToken cancellationToken)
    {
        var jobs = await dbContext.Jobs.AsNoTracking().ToListAsync(cancellationToken);
        var assets = await dbContext.ContentAssets.AsNoTracking().ToListAsync(cancellationToken);
        var accounts = await dbContext.Accounts.AsNoTracking().ToListAsync(cancellationToken);
        var affiliateProducts = await dbContext.AffiliateProducts.AsNoTracking().ToListAsync(cancellationToken);
        var revenue = await dbContext.RevenueRecords.AsNoTracking().SumAsync(item => (decimal?)item.Amount, cancellationToken) ?? 0m;
        var cost = await dbContext.CostLedgerEntries.AsNoTracking().SumAsync(item => (decimal?)item.Amount, cancellationToken) ?? 0m;

        var completedJobs = jobs.Where(job => job.StartedAt.HasValue && job.CompletedAt.HasValue).ToList();
        var avgDurationSeconds = completedJobs.Count == 0
            ? 0
            : completedJobs.Average(job => (job.CompletedAt!.Value - job.StartedAt!.Value).TotalSeconds);

        var successfulJobs = jobs.Count(job => job.Status == "succeeded");
        var failedJobs = jobs.Count(job => job.Status == "failed");
        var outreachEmailsSent = jobs.Where(job => job.Type == "outreach_run").Sum(job => ReadMetric(job.ResultJson, "emailsSent"));

        return Results.Ok(new
        {
            generatedAt = DateTimeOffset.UtcNow,
            kpis = new[]
            {
                Card("Jobs run", jobs.Count, "Total queued and completed automation work."),
                Card("Success rate", Percentage(successfulJobs, jobs.Count), "Share of jobs that reached a succeeded state."),
                Card("Failure rate", Percentage(failedJobs, jobs.Count), "Share of jobs that ended in failure."),
                Card("Videos published", assets.Count(asset => asset.Kind == "youtube_video"), "Imported or newly published YouTube outputs."),
                Card("Tweets posted", assets.Count(asset => asset.Kind == "twitter_post"), "Imported or newly posted X content."),
                Card("Outreach emails", outreachEmailsSent, "Emails reported by outreach job runs."),
                Card("Avg duration", Math.Round(avgDurationSeconds, 1), "Average job runtime in seconds."),
                Card("Active accounts", accounts.Count(account => account.LastActiveAt.HasValue), "Accounts with recorded recent activity."),
                Card("Affiliate products", affiliateProducts.Count, "Tracked products ready for affiliate promotion."),
                Card("Total commission", revenue, "Revenue records imported into the control plane."),
                Card("Estimated cost", cost, "Costs logged against jobs and platform operations."),
                Card("Net profit", revenue - cost, "Commission minus cost ledger entries.")
            },
            recentJobs = jobs.OrderByDescending(job => job.CreatedAt).Take(8).Select(job => new
            {
                job.Id,
                job.Type,
                job.Status,
                job.Provider,
                job.CreatedAt,
                job.CompletedAt
            }),
            activeAccounts = accounts.OrderByDescending(account => account.LastActiveAt).Take(6).Select(account => new
            {
                account.Id,
                account.Provider,
                account.Nickname,
                account.LastActiveAt,
                account.LastFailureAt,
                account.LastError
            })
        });
    }

    private static async Task<IResult> GetAccountsAsync(CreatorGrowthControlPlaneDbContext dbContext, CancellationToken cancellationToken)
    {
        var accounts = await dbContext.Accounts
            .AsNoTracking()
            .OrderBy(account => account.Provider)
            .ThenBy(account => account.Nickname)
            .Select(account => new
            {
                account.Id,
                account.Provider,
                account.Nickname,
                account.Topic,
                account.Niche,
                account.Language,
                account.LastActiveAt,
                account.LastFailureAt,
                account.LastError,
                assetCount = account.Assets.Count
            })
            .ToListAsync(cancellationToken);

        return Results.Ok(accounts);
    }

    private static async Task<IResult> UpdateAccountAsync(
        string accountId,
        UpdateAccountDto dto,
        CreatorGrowthControlPlaneDbContext dbContext,
        IWebHostEnvironment environment,
        CancellationToken cancellationToken)
    {
        var account = await dbContext.Accounts.FirstOrDefaultAsync(item => item.Id == accountId, cancellationToken);
        if (account is null)
        {
            return Results.NotFound();
        }

        if (dto.Topic is not null)
        {
            account.Topic = string.IsNullOrWhiteSpace(dto.Topic) ? null : dto.Topic.Trim();
        }

        if (dto.Niche is not null)
        {
            account.Niche = string.IsNullOrWhiteSpace(dto.Niche) ? null : dto.Niche.Trim();
        }

        if (dto.Language is not null)
        {
            account.Language = string.IsNullOrWhiteSpace(dto.Language) ? null : dto.Language.Trim();
        }

        if (string.Equals(account.Provider, "youtube", StringComparison.OrdinalIgnoreCase) && dto.Topic is not null && dto.Niche is null)
        {
            account.Niche = account.Topic;
        }

        await dbContext.SaveChangesAsync(cancellationToken);

        string? syncWarning = null;
        try
        {
            await SyncAccountToLegacyCacheAsync(environment, account, cancellationToken);
        }
        catch (Exception exc)
        {
            syncWarning = $"Saved in database, but legacy cache sync failed: {exc.Message}";
        }

        return Results.Ok(new
        {
            account.Id,
            account.Provider,
            account.Nickname,
            account.Topic,
            account.Niche,
            account.Language,
            account.LastActiveAt,
            account.LastFailureAt,
            account.LastError,
            syncWarning
        });
    }

    private static async Task<IResult> GetContentAsync(CreatorGrowthControlPlaneDbContext dbContext, CancellationToken cancellationToken)
    {
        var assets = await dbContext.ContentAssets
            .AsNoTracking()
            .OrderByDescending(asset => asset.PublishedAt)
            .Take(100)
            .Select(asset => new
            {
                asset.Id,
                asset.Kind,
                asset.Provider,
                asset.AccountId,
                asset.Title,
                asset.Description,
                asset.Url,
                asset.LocalPath,
                asset.Views,
                asset.Clicks,
                asset.Revenue,
                asset.Cost,
                asset.PublishedAt
            })
            .ToListAsync(cancellationToken);

        return Results.Ok(assets);
    }

    private static async Task<IResult> GetAffiliateOverviewAsync(CreatorGrowthControlPlaneDbContext dbContext, CancellationToken cancellationToken)
    {
        var products = await dbContext.AffiliateProducts
            .AsNoTracking()
            .OrderByDescending(product => product.CreatedAt)
            .Select(product => new
            {
                product.Id,
                product.AffiliateLink,
                product.AccountId,
                product.AccountNickname,
                product.Name,
                product.CreatedAt
            })
            .ToListAsync(cancellationToken);

        var revenue = await dbContext.RevenueRecords
            .AsNoTracking()
            .Where(record => record.ProductId != null)
            .GroupBy(record => record.ProductId)
            .Select(group => new
            {
                productId = group.Key,
                revenue = group.Sum(item => item.Amount),
                clicks = group.Sum(item => item.Clicks ?? 0),
                conversions = group.Sum(item => item.Conversions ?? 0)
            })
            .ToListAsync(cancellationToken);

        return Results.Ok(new { products, revenue });
    }

    private static async Task<IResult> GetProfitAsync(CreatorGrowthControlPlaneDbContext dbContext, CancellationToken cancellationToken)
    {
        var revenue = await dbContext.RevenueRecords.AsNoTracking().OrderByDescending(item => item.OccurredAt).ToListAsync(cancellationToken);
        var cost = await dbContext.CostLedgerEntries.AsNoTracking().OrderByDescending(item => item.OccurredAt).ToListAsync(cancellationToken);

        return Results.Ok(new
        {
            revenue,
            cost,
            totals = new
            {
                revenue = revenue.Sum(item => item.Amount),
                cost = cost.Sum(item => item.Amount),
                profit = revenue.Sum(item => item.Amount) - cost.Sum(item => item.Amount)
            }
        });
    }

    private static async Task<IResult> GetOutreachLeadsAsync(IWebHostEnvironment environment, CancellationToken cancellationToken)
    {
        var repositoryRoot = ResolveRepositoryRoot(environment);
        var sourcePath = Path.Combine(repositoryRoot, ".mp", "scraper_results.csv");
        if (!File.Exists(sourcePath))
        {
            return Results.Ok(new
            {
                generatedAt = DateTimeOffset.UtcNow,
                sourcePath,
                leadCount = 0,
                readyCount = 0,
                websiteOnlyCount = 0,
                missingContactCount = 0,
                rows = Array.Empty<object>()
            });
        }

        var lines = await File.ReadAllLinesAsync(sourcePath, cancellationToken);
        if (lines.Length == 0)
        {
            return Results.Ok(new
            {
                generatedAt = DateTimeOffset.UtcNow,
                sourcePath,
                leadCount = 0,
                readyCount = 0,
                websiteOnlyCount = 0,
                missingContactCount = 0,
                rows = Array.Empty<object>()
            });
        }

        var headers = ParseCsvLine(lines[0]).Select(item => item.Trim()).ToList();
        var rows = new List<object>();
        var readyCount = 0;
        var websiteOnlyCount = 0;
        var missingContactCount = 0;

        for (var index = 1; index < lines.Length; index++)
        {
            var line = lines[index];
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            var cells = ParseCsvLine(line);
            var title = ReadCell(headers, cells, "title");
            var category = ReadCell(headers, cells, "category");
            var address = ReadCell(headers, cells, "address");
            var websiteRaw = ReadCell(headers, cells, "website");
            var website = NormalizeWebsiteUrl(websiteRaw);
            var phone = ReadCell(headers, cells, "phone");
            var plusCode = ReadCell(headers, cells, "plus_code");
            var reviewCount = ReadCell(headers, cells, "review_count");
            var reviewRating = ReadCell(headers, cells, "review_rating");

            var email = ReadCell(headers, cells, "email");
            if (string.IsNullOrWhiteSpace(email) && cells.Count > headers.Count)
            {
                email = cells[^1].Trim();
            }

            var status = "missing_contact";
            if (!string.IsNullOrWhiteSpace(email) && email.Contains('@'))
            {
                status = "ready";
                readyCount++;
            }
            else if (!string.IsNullOrWhiteSpace(website))
            {
                status = "website_only";
                websiteOnlyCount++;
            }
            else
            {
                missingContactCount++;
            }

            rows.Add(new
            {
                id = $"lead-{index}",
                title,
                category,
                address,
                website,
                phone,
                plusCode,
                reviewCount,
                reviewRating,
                email,
                status
            });
        }

        return Results.Ok(new
        {
            generatedAt = DateTimeOffset.UtcNow,
            sourcePath,
            leadCount = rows.Count,
            readyCount,
            websiteOnlyCount,
            missingContactCount,
            rows
        });
    }

    private static object Card(string label, object value, string hint) => new { label, value, hint };

    private static string Percentage(int numerator, int denominator)
    {
        if (denominator == 0)
        {
            return "0%";
        }

        return $"{Math.Round((double)numerator / denominator * 100, 1)}%";
    }

    private static int ReadMetric(string? resultJson, string key)
    {
        if (string.IsNullOrWhiteSpace(resultJson))
        {
            return 0;
        }

        try
        {
            var root = JsonNode.Parse(resultJson);
            return root?["metrics"]?[key]?.GetValue<int>() ?? 0;
        }
        catch
        {
            return 0;
        }
    }

    private static string ResolveRepositoryRoot(IWebHostEnvironment environment)
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

    private static string ReadCell(IReadOnlyList<string> headers, IReadOnlyList<string> cells, string name)
    {
        var index = headers
            .Select((header, position) => new { header, position })
            .FirstOrDefault(item => string.Equals(item.header, name, StringComparison.OrdinalIgnoreCase))
            ?.position ?? -1;

        if (index < 0 || index >= cells.Count)
        {
            return string.Empty;
        }

        return cells[index].Trim();
    }

    private static List<string> ParseCsvLine(string line)
    {
        var results = new List<string>();
        var buffer = new StringBuilder();
        var inQuotes = false;

        for (var i = 0; i < line.Length; i++)
        {
            var current = line[i];
            if (current == '"')
            {
                if (inQuotes && i + 1 < line.Length && line[i + 1] == '"')
                {
                    buffer.Append('"');
                    i++;
                }
                else
                {
                    inQuotes = !inQuotes;
                }

                continue;
            }

            if (current == ',' && !inQuotes)
            {
                results.Add(buffer.ToString());
                buffer.Clear();
                continue;
            }

            buffer.Append(current);
        }

        results.Add(buffer.ToString());
        return results;
    }

    private static string NormalizeWebsiteUrl(string rawUrl)
    {
        if (string.IsNullOrWhiteSpace(rawUrl))
        {
            return string.Empty;
        }

        var trimmed = rawUrl.Trim();
        if (trimmed.StartsWith("/url?", StringComparison.OrdinalIgnoreCase))
        {
            var query = trimmed[(trimmed.IndexOf('?') + 1)..];
            foreach (var pair in query.Split('&', StringSplitOptions.RemoveEmptyEntries))
            {
                var parts = pair.Split('=', 2);
                if (parts.Length != 2 || !string.Equals(parts[0], "q", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                trimmed = Uri.UnescapeDataString(parts[1]);
                break;
            }
        }

        return trimmed.StartsWith("http://", StringComparison.OrdinalIgnoreCase)
            || trimmed.StartsWith("https://", StringComparison.OrdinalIgnoreCase)
            ? trimmed
            : string.Empty;
    }

    private static async Task SyncAccountToLegacyCacheAsync(
        IWebHostEnvironment environment,
        Domain.AccountEntity account,
        CancellationToken cancellationToken)
    {
        var provider = account.Provider.ToLowerInvariant();
        if (provider is not ("twitter" or "youtube"))
        {
            return;
        }

        var repositoryRoot = ResolveRepositoryRoot(environment);
        var cachePath = Path.Combine(repositoryRoot, ".mp", $"{provider}.json");
        if (!File.Exists(cachePath))
        {
            return;
        }

        JsonNode? root;
        try
        {
            var raw = await File.ReadAllTextAsync(cachePath, cancellationToken);
            root = JsonNode.Parse(raw);
        }
        catch
        {
            return;
        }

        if (root is null)
        {
            return;
        }

        var accounts = root["accounts"]?.AsArray();
        if (accounts is null)
        {
            return;
        }

        var matched = accounts
            .OfType<JsonObject>()
            .FirstOrDefault(item => string.Equals(item["id"]?.GetValue<string>(), account.Id, StringComparison.OrdinalIgnoreCase));
        if (matched is null)
        {
            return;
        }

        if (provider == "twitter")
        {
            matched["topic"] = account.Topic ?? string.Empty;
        }
        else
        {
            matched["topic"] = account.Topic ?? account.Niche ?? string.Empty;
            matched["niche"] = account.Niche ?? account.Topic ?? string.Empty;
            matched["language"] = account.Language ?? string.Empty;
        }

        var json = root.ToJsonString(new JsonSerializerOptions { WriteIndented = true });
        await File.WriteAllTextAsync(cachePath, json, cancellationToken);
    }
}

public sealed record UpdateAccountDto(string? Topic, string? Niche, string? Language);

