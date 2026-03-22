using CreatorGrowthControlPlane.Orchestrator.Data;
using CreatorGrowthControlPlane.Orchestrator.Domain;
using Microsoft.EntityFrameworkCore;
using StackExchange.Redis;
using System.Text.Json;

namespace CreatorGrowthControlPlane.Orchestrator.Endpoints;

public static class SettingsEndpoints
{
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

        return Results.Ok(new
        {
            settings.OpenAIApiKey,
            settings.GeminiApiKey,
            settings.ActiveModelProvider,
            settings.OllamaModelName
        });
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
        settings.ActiveModelProvider = dto.ActiveModelProvider ?? "ollama";
        settings.OllamaModelName = dto.OllamaModelName ?? "llama3";

        await dbContext.SaveChangesAsync(cancellationToken);

        var finalResponse = new
        {
            settings.OpenAIApiKey,
            settings.GeminiApiKey,
            settings.ActiveModelProvider,
            settings.OllamaModelName
        };

        var cacheDb = redis.GetDatabase();
        await cacheDb.StringSetAsync("cgcp:settings", JsonSerializer.Serialize(finalResponse));

        return Results.Ok(finalResponse);
    }
}

public record GlobalSettingsUpdateDto(
    string? OpenAIApiKey,
    string? GeminiApiKey,
    string? ActiveModelProvider,
    string? OllamaModelName
);
