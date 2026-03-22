using CreatorGrowthControlPlane.Orchestrator.Data;
using CreatorGrowthControlPlane.Orchestrator.Domain;
using Microsoft.EntityFrameworkCore;
using StackExchange.Redis;
using System.Text.Json;

namespace CreatorGrowthControlPlane.Orchestrator.Endpoints;

public static class SystemPromptEndpoints
{
    private static readonly List<SystemPromptEntity> DefaultPrompts = new()
    {
        new SystemPromptEntity
        {
            Id = Guid.NewGuid(),
            Key = "youtube_topic_generation",
            Description = "Generates a highly engaging topic for a YouTube Short.",
            PromptText = "You are an expert YouTube content strategist. Please generate a highly engaging, specific, and viral-worthy video topic idea related to the following niche: {niche}. Make your response exactly one concise sentence. Do not include any conversational filler, only return the topic itself."
        },
        new SystemPromptEntity
        {
            Id = Guid.NewGuid(),
            Key = "youtube_script_generation",
            Description = "Generates the voiceover script for the video.",
            PromptText = "You are a professional YouTube scriptwriter known for retaining high viewer attention. Write a script for a video about {subject} in exactly {sentence_length} short, punchy sentences. Show the result early and structure the narrative by chapter. Give brief directional notes to refresh the visual every 20-30 seconds. DO NOT INCLUDE ANY FORMATTING LIKE 'VOICEOVER:' OR MENTION THIS PROMPT."
        },
        new SystemPromptEntity
        {
            Id = Guid.NewGuid(),
            Key = "youtube_metadata_title",
            Description = "Generates an SEO-optimized title for the short.",
            PromptText = "You are an expert YouTube SEO specialist. Generate a highly clickable, high-retention title for the following video subject: {subject}. Include relevant hashtags. Maximum 100 characters. Return ONLY the title without quotes or extra text."
        },
        new SystemPromptEntity
        {
            Id = Guid.NewGuid(),
            Key = "youtube_metadata_description",
            Description = "Generates an SEO-optimized description.",
            PromptText = "You are an expert YouTube SEO specialist. Write a captivating description for the following script: {script}. Optimize for searchability and engagement. Return ONLY the description text, nothing else."
        },
        new SystemPromptEntity
        {
            Id = Guid.NewGuid(),
            Key = "youtube_image_prompts",
            Description = "Generates image prompts for AI image generation.",
            PromptText = "You are an expert AI image generation director. Generate exactly {n_prompts} distinct, highly detailed, and emotional image prompts that visually represent key moments of the following video subject: {subject}.\nReturn STRICTLY a JSON array of strings in the format: [\"prompt 1\", \"prompt 2\"]. Do not include markdown formatting like ```json or any conversational text. For context, here is the script: {script}."
        },
        new SystemPromptEntity
        {
            Id = Guid.NewGuid(),
            Key = "short_from_longform_script",
            Description = "Summarizes long-form content into a punchy short script.",
            PromptText = "You are an expert at repurposing long-form content into engaging short-form video scripts (like TikTok or YouTube Shorts). Summarize the following long form content into a highly engaging {sentence_length}-sentence script. Make it punchy, hook the viewer in the first 3 seconds, and deliver one clear idea. DO NOT INCLUDE ANY FORMATTING LIKE 'VOICEOVER:' OR MENTION THE PROMPT. ONLY RETURN THE SCRIPT TEXT.\n\nContent:\n{content}"
        },
        new SystemPromptEntity
        {
            Id = Guid.NewGuid(),
            Key = "twitter_post_generation",
            Description = "Generates a highly engaging X (Twitter) post based on the content engine playbook.",
            PromptText = "You are an expert X (Twitter) content creator. Write exactly one fast-opening, highly engaging post about {topic}. Rules: Open fast. One clear idea per post. Hooks matter more than summaries. Use specifics over slogans. Keep links out of the main body unless necessary. Avoid hash-tag spam. Only return the raw text of the post."
        },
        new SystemPromptEntity
        {
            Id = Guid.NewGuid(),
            Key = "afm_pitch",
            Description = "Generates an affiliate marketing pitch following content-engine rules.",
            PromptText = "You are an expert promotional copywriter. Write a highly engaging pitch for: {title}. Features: {features}. Rules: Open fast. Deliver one clear outcome. Focus on specifics over hype slogans. Maximum 2 short paragraphs. Only return the pitch text."
        }
    };

    public static IEndpointRouteBuilder MapSystemPromptEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/prompts");
        group.MapGet("", GetPromptsAsync);
        group.MapPost("", CreatePromptAsync);
        group.MapPut("/{id:guid}", UpdatePromptAsync);
        group.MapDelete("/{id:guid}", DeletePromptAsync);
        return app;
    }

    private static async Task<IResult> GetPromptsAsync(CreatorGrowthControlPlaneDbContext dbContext, CancellationToken cancellationToken)
    {
        var prompts = await dbContext.SystemPrompts.OrderBy(p => p.Key).ToListAsync(cancellationToken);
        
        // Seed if empty
        if (prompts.Count == 0)
        {
            await dbContext.SystemPrompts.AddRangeAsync(DefaultPrompts, cancellationToken);
            await dbContext.SaveChangesAsync(cancellationToken);
            prompts = await dbContext.SystemPrompts.OrderBy(p => p.Key).ToListAsync(cancellationToken);
        }

        return Results.Ok(prompts.Select(p => new
        {
            p.Id,
            p.Key,
            p.Description,
            p.PromptText,
            p.UpdatedAt
        }));
    }

    private static async Task<IResult> UpdatePromptAsync(
        Guid id,
        UpdatePromptDto dto,
        CreatorGrowthControlPlaneDbContext dbContext,
        IConnectionMultiplexer redis,
        CancellationToken cancellationToken)
    {
        var prompt = await dbContext.SystemPrompts.FirstOrDefaultAsync(p => p.Id == id, cancellationToken);
        if (prompt is null)
        {
            return Results.NotFound();
        }

        prompt.PromptText = dto.PromptText;
        prompt.UpdatedAt = DateTime.UtcNow;

        await dbContext.SaveChangesAsync(cancellationToken);

        // Update Redis cache asynchronously so python reads it instantly
        await CachePromptsToRedisAsync(dbContext, redis, cancellationToken);

        return Results.Ok(new
        {
            prompt.Id,
            prompt.Key,
            prompt.Description,
            prompt.PromptText,
            prompt.UpdatedAt
        });
    }

    private static async Task<IResult> CreatePromptAsync(
        CreatePromptDto dto,
        CreatorGrowthControlPlaneDbContext dbContext,
        IConnectionMultiplexer redis,
        CancellationToken cancellationToken)
    {
        var prompt = new SystemPromptEntity
        {
            Id = Guid.NewGuid(),
            Key = dto.Key,
            Description = dto.Description,
            PromptText = dto.PromptText
        };

        dbContext.SystemPrompts.Add(prompt);
        await dbContext.SaveChangesAsync(cancellationToken);

        await CachePromptsToRedisAsync(dbContext, redis, cancellationToken);

        return Results.Ok(new
        {
            prompt.Id,
            prompt.Key,
            prompt.Description,
            prompt.PromptText,
            prompt.UpdatedAt
        });
    }

    private static async Task<IResult> DeletePromptAsync(
        Guid id,
        CreatorGrowthControlPlaneDbContext dbContext,
        IConnectionMultiplexer redis,
        CancellationToken cancellationToken)
    {
        var prompt = await dbContext.SystemPrompts.FirstOrDefaultAsync(p => p.Id == id, cancellationToken);
        if (prompt is null)
        {
            return Results.NotFound();
        }

        dbContext.SystemPrompts.Remove(prompt);
        await dbContext.SaveChangesAsync(cancellationToken);

        await CachePromptsToRedisAsync(dbContext, redis, cancellationToken);

        return Results.NoContent();
    }

    private static async Task CachePromptsToRedisAsync(
        CreatorGrowthControlPlaneDbContext dbContext, 
        IConnectionMultiplexer redis, 
        CancellationToken cancellationToken)
    {
        var prompts = await dbContext.SystemPrompts.OrderBy(p => p.Key).ToListAsync(cancellationToken);
        var dto = prompts.Select(p => new { p.Key, p.PromptText });
        var cacheDb = redis.GetDatabase();
        await cacheDb.StringSetAsync("cgcp:prompts", JsonSerializer.Serialize(dto));
    }
}

public record UpdatePromptDto(string PromptText);
public record CreatePromptDto(string Key, string Description, string PromptText);
