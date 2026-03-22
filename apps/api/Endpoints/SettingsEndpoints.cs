using CreatorGrowthControlPlane.Orchestrator.Data;
using CreatorGrowthControlPlane.Orchestrator.Domain;
using Microsoft.EntityFrameworkCore;
using StackExchange.Redis;
using System.Text.Json;

namespace CreatorGrowthControlPlane.Orchestrator.Endpoints;

public static class SettingsEndpoints
{
    private static readonly Dictionary<string, string[]> ProviderModelCatalog = new(StringComparer.OrdinalIgnoreCase)
    {
        ["ollama"] =
        [
            "llama3.2:3b",
            "llama3.2:1b",
            "qwen2.5:7b",
            "mistral:7b",
            "gemma2:9b"
        ],
        ["openai"] =
        [
            "gpt-4o-mini",
            "gpt-4.1-mini",
            "gpt-4.1",
            "gpt-4o"
        ],
        ["gemini"] =
        [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash"
        ]
    };

    public static IEndpointRouteBuilder MapSettingsEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/settings");
        group.MapGet("", GetSettingsAsync);
        group.MapPost("", UpdateSettingsAsync);
        return app;
    }

    private static async Task<IResult> GetSettingsAsync(CreatorGrowthControlPlaneDbContext dbContext, CancellationToken cancellationToken)
    {
        var settings = await dbContext.GlobalSettings.FirstOrDefaultAsync(cancellationToken);
        if (settings is null)
        {
            settings = new GlobalSettingsEntity();
            dbContext.GlobalSettings.Add(settings);
            await dbContext.SaveChangesAsync(cancellationToken);
        }

        settings.ActiveModelProvider = NormalizeProvider(settings.ActiveModelProvider);
        settings.OllamaModelName = ResolveModel("ollama", settings.OllamaModelName);
        settings.OpenAIModelName = ResolveModel("openai", settings.OpenAIModelName);
        settings.GeminiModelName = ResolveModel("gemini", settings.GeminiModelName);

        await dbContext.SaveChangesAsync(cancellationToken);

        return Results.Ok(BuildSettingsResponse(settings));
    }

    private static async Task<IResult> UpdateSettingsAsync(
        GlobalSettingsUpdateDto dto,
        CreatorGrowthControlPlaneDbContext dbContext,
        IConnectionMultiplexer redis,
        CancellationToken cancellationToken)
    {
        var settings = await dbContext.GlobalSettings.FirstOrDefaultAsync(cancellationToken);
        if (settings is null)
        {
            settings = new GlobalSettingsEntity();
            dbContext.GlobalSettings.Add(settings);
        }

        settings.OpenAIApiKey = dto.OpenAIApiKey;
        settings.GeminiApiKey = dto.GeminiApiKey;
        settings.ActiveModelProvider = NormalizeProvider(dto.ActiveModelProvider);
        settings.OllamaModelName = ResolveModel("ollama", dto.OllamaModelName);
        settings.OpenAIModelName = ResolveModel("openai", dto.OpenAIModelName);
        settings.GeminiModelName = ResolveModel("gemini", dto.GeminiModelName);

        await dbContext.SaveChangesAsync(cancellationToken);

        var finalResponse = BuildSettingsResponse(settings);

        var cacheDb = redis.GetDatabase();
        await cacheDb.StringSetAsync("cgcp:settings", JsonSerializer.Serialize(finalResponse));

        return Results.Ok(finalResponse);
    }

    private static object BuildSettingsResponse(GlobalSettingsEntity settings)
    {
        var activeProvider = NormalizeProvider(settings.ActiveModelProvider);
        var activeProviderApiKey = activeProvider switch
        {
            "openai" => settings.OpenAIApiKey,
            "gemini" => settings.GeminiApiKey,
            _ => null
        };

        return new
        {
            settings.OpenAIApiKey,
            settings.GeminiApiKey,
            settings.ActiveModelProvider,
            settings.OllamaModelName,
            settings.OpenAIModelName,
            settings.GeminiModelName,
            modelCatalog = ProviderModelCatalog,
            hasOpenAIApiKey = !string.IsNullOrWhiteSpace(settings.OpenAIApiKey),
            hasGeminiApiKey = !string.IsNullOrWhiteSpace(settings.GeminiApiKey),
            activeProviderApiKeyConfigured = !string.IsNullOrWhiteSpace(activeProviderApiKey),
            activeProviderApiKeyMasked = MaskApiKey(activeProviderApiKey)
        };
    }

    private static string NormalizeProvider(string? provider)
    {
        var normalized = (provider ?? "ollama").Trim().ToLowerInvariant();
        return ProviderModelCatalog.ContainsKey(normalized) ? normalized : "ollama";
    }

    private static string ResolveModel(string provider, string? selectedModel)
    {
        var options = ProviderModelCatalog[provider];
        var candidate = (selectedModel ?? string.Empty).Trim();
        if (candidate.Length == 0)
        {
            return options[0];
        }

        var match = options.FirstOrDefault(option => option.Equals(candidate, StringComparison.OrdinalIgnoreCase));
        return match ?? options[0];
    }

    private static string? MaskApiKey(string? apiKey)
    {
        if (string.IsNullOrWhiteSpace(apiKey))
        {
            return null;
        }

        var value = apiKey.Trim();
        if (value.Length <= 8)
        {
            return "********";
        }

        return $"{value[..4]}...{value[^4..]}";
    }
}

public record GlobalSettingsUpdateDto(
    string? OpenAIApiKey,
    string? GeminiApiKey,
    string? ActiveModelProvider,
    string? OllamaModelName,
    string? OpenAIModelName,
    string? GeminiModelName
);
