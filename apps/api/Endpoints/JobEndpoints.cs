using System.Text.Json;
using CreatorGrowthControlPlane.Orchestrator.Contracts;
using CreatorGrowthControlPlane.Orchestrator.Data;
using CreatorGrowthControlPlane.Orchestrator.Domain;
using CreatorGrowthControlPlane.Orchestrator.Infrastructure;
using CreatorGrowthControlPlane.Orchestrator.Services;
using Microsoft.EntityFrameworkCore;

namespace CreatorGrowthControlPlane.Orchestrator.Endpoints;

public static class JobEndpoints
{
    private static readonly JsonSerializerOptions StreamSerializerOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase
    };

    public static IEndpointRouteBuilder MapJobEndpoints(this IEndpointRouteBuilder app)
    {
        var jobs = app.MapGroup("/api/jobs");
        jobs.MapGet("", GetJobsAsync);
        jobs.MapGet("/stream", StreamJobsAsync);
        jobs.MapGet("/{jobId:guid}", GetJobAsync);
        jobs.MapGet("/{jobId:guid}/events", GetJobEventsAsync);
        jobs.MapPost("", CreateJobAsync);
        jobs.MapPost("/{jobId:guid}/cancel", CancelJobAsync);

        var internalGroup = app.MapGroup("/api/internal");
        internalGroup.MapPost("/jobs/{jobId:guid}/status", UpdateJobStatusAsync);
        internalGroup.MapPost("/jobs/{jobId:guid}/events", AddJobEventAsync);
        internalGroup.MapPost("/legacy/sync", SyncLegacyAsync);

        return app;
    }

    private static async Task<IResult> GetJobsAsync(CreatorGrowthControlPlaneDbContext dbContext, CancellationToken cancellationToken)
    {
        var jobs = await dbContext.Jobs
            .AsNoTracking()
            .OrderByDescending(job => job.CreatedAt)
            .Take(50)
            .Select(job => new
            {
                job.Id,
                job.Type,
                job.Status,
                job.Provider,
                job.AccountId,
                job.ProductId,
                job.Model,
                job.CreatedAt,
                job.StartedAt,
                job.CompletedAt,
                job.ErrorMessage
            })
            .ToListAsync(cancellationToken);

        return Results.Ok(jobs.Select(job => new
        {
            job.Id,
            job.Type,
            job.Status,
            job.Provider,
            job.AccountId,
            job.ProductId,
            job.Model,
            job.CreatedAt,
            job.StartedAt,
            job.CompletedAt,
            ErrorMessage = TrimText(job.ErrorMessage, 220)
        }));
    }

    private static async Task StreamJobsAsync(HttpContext httpContext, CreatorGrowthControlPlaneDbContext dbContext, CancellationToken cancellationToken)
    {
        httpContext.Response.Headers.CacheControl = "no-cache";
        httpContext.Response.Headers.Append("X-Accel-Buffering", "no");
        httpContext.Response.ContentType = "text/event-stream";

        var selectedJobId = Guid.TryParse(httpContext.Request.Query["jobId"], out var parsedJobId)
            ? parsedJobId
            : (Guid?)null;

        string? lastPayload = null;

        try
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                var jobs = await dbContext.Jobs
                    .AsNoTracking()
                    .OrderByDescending(job => job.CreatedAt)
                    .Take(50)
                    .Select(job => new
                    {
                        job.Id,
                        job.Type,
                        job.Status,
                        job.Provider,
                        job.AccountId,
                        job.ProductId,
                        job.Model,
                        job.CreatedAt,
                        job.StartedAt,
                        job.CompletedAt,
                        job.ErrorMessage
                    })
                    .ToListAsync(cancellationToken);

                var compactJobs = jobs.Select(job => new
                {
                    job.Id,
                    job.Type,
                    job.Status,
                    job.Provider,
                    job.AccountId,
                    job.ProductId,
                    job.Model,
                    job.CreatedAt,
                    job.StartedAt,
                    job.CompletedAt,
                    ErrorMessage = TrimText(job.ErrorMessage, 220)
                });

                object? selectedJob = null;
                if (selectedJobId.HasValue)
                {
                    var job = await dbContext.Jobs
                        .AsNoTracking()
                        .Include(item => item.Events)
                        .FirstOrDefaultAsync(item => item.Id == selectedJobId.Value, cancellationToken);

                    if (job is not null)
                    {
                        selectedJob = new
                        {
                            job.Id,
                            job.Type,
                            job.Status,
                            job.Provider,
                            job.AccountId,
                            job.ProductId,
                            job.Model,
                            job.PayloadJson,
                            job.ResultJson,
                            ErrorMessage = TrimText(job.ErrorMessage, 1200),
                            job.CreatedAt,
                            job.StartedAt,
                            job.CompletedAt,
                            events = job.Events
                                .OrderBy(eventItem => eventItem.CreatedAt)
                                .Select(eventItem => new
                                {
                                    eventItem.Id,
                                    eventItem.Level,
                                    eventItem.Step,
                                    eventItem.Message,
                                    eventItem.CreatedAt
                                })
                        };
                    }
                }

                var payload = JsonSerializer.Serialize(new
                {
                    timestamp = DateTimeOffset.UtcNow,
                    jobs = compactJobs,
                    selectedJob
                }, StreamSerializerOptions);

                if (!string.Equals(payload, lastPayload, StringComparison.Ordinal))
                {
                    await httpContext.Response.WriteAsync("event: jobs\n", cancellationToken);
                    await httpContext.Response.WriteAsync($"data: {payload}\n\n", cancellationToken);
                    await httpContext.Response.Body.FlushAsync(cancellationToken);
                    lastPayload = payload;
                }
                else
                {
                    await httpContext.Response.WriteAsync($": keepalive {DateTimeOffset.UtcNow.ToUnixTimeSeconds()}\n\n", cancellationToken);
                    await httpContext.Response.Body.FlushAsync(cancellationToken);
                }

                await Task.Delay(TimeSpan.FromSeconds(1), cancellationToken);
            }
        }
        catch (OperationCanceledException)
        {
            // Client disconnected or request cancelled.
        }
    }

    private static async Task<IResult> GetJobAsync(Guid jobId, CreatorGrowthControlPlaneDbContext dbContext, CancellationToken cancellationToken)
    {
        var job = await dbContext.Jobs
            .AsNoTracking()
            .Include(item => item.Events)
            .FirstOrDefaultAsync(item => item.Id == jobId, cancellationToken);

        return job is null
            ? Results.NotFound()
            : Results.Ok(new
            {
                job.Id,
                job.Type,
                job.Status,
                job.Provider,
                job.AccountId,
                job.ProductId,
                job.Model,
                job.PayloadJson,
                job.ResultJson,
                job.ErrorMessage,
                job.CreatedAt,
                job.StartedAt,
                job.CompletedAt,
                events = job.Events
                    .OrderBy(eventItem => eventItem.CreatedAt)
                    .Select(eventItem => new
                    {
                        eventItem.Id,
                        eventItem.Level,
                        eventItem.Step,
                        eventItem.Message,
                        eventItem.CreatedAt
                    })
            });
    }

    private static async Task<IResult> GetJobEventsAsync(Guid jobId, CreatorGrowthControlPlaneDbContext dbContext, CancellationToken cancellationToken)
    {
        var events = await dbContext.JobEvents
            .AsNoTracking()
            .Where(eventItem => eventItem.JobId == jobId)
            .OrderBy(eventItem => eventItem.CreatedAt)
            .Select(eventItem => new
            {
                eventItem.Id,
                eventItem.Level,
                eventItem.Step,
                eventItem.Message,
                eventItem.CreatedAt
            })
            .ToListAsync(cancellationToken);

        return Results.Ok(events);
    }

    private static async Task<IResult> CreateJobAsync(
        CreateJobRequest request,
        CreatorGrowthControlPlaneDbContext dbContext,
        RedisQueuePublisher queuePublisher,
        CancellationToken cancellationToken)
    {
        var job = new JobEntity
        {
            Id = Guid.NewGuid(),
            Type = request.Type,
            Provider = request.Provider ?? InferProvider(request.Type),
            Status = "queued",
            AccountId = request.AccountId,
            ProductId = request.ProductId,
            Model = request.Model,
            PayloadJson = JsonSerializer.Serialize(request.Parameters ?? new Dictionary<string, string?>())
        };

        dbContext.Jobs.Add(job);
        dbContext.JobEvents.Add(new JobEventEntity
        {
            JobId = job.Id,
            Level = "info",
            Step = "queued",
            Message = $"Queued {job.Type} job for provider {job.Provider}."
        });
        await dbContext.SaveChangesAsync(cancellationToken);

        await queuePublisher.EnqueueAsync(new
        {
            jobId = job.Id,
            type = job.Type,
            provider = job.Provider,
            accountId = job.AccountId,
            productId = job.ProductId,
            model = job.Model,
            parameters = request.Parameters ?? new Dictionary<string, string?>()
        });

        return Results.Created($"/api/jobs/{job.Id}", new { jobId = job.Id, status = job.Status });
    }

    private static async Task<IResult> UpdateJobStatusAsync(
        Guid jobId,
        JobStatusUpdateRequest request,
        CreatorGrowthControlPlaneDbContext dbContext,
        CancellationToken cancellationToken)
    {
        var job = await dbContext.Jobs.FirstOrDefaultAsync(item => item.Id == jobId, cancellationToken);
        if (job is null)
        {
            return Results.NotFound();
        }

        if (job.Status == "cancelled" && !string.Equals(request.Status, "cancelled", StringComparison.OrdinalIgnoreCase))
        {
            return Results.Ok(new { jobId = job.Id, status = job.Status, ignored = true });
        }

        job.Status = request.Status;
        job.ErrorMessage = request.ErrorMessage;
        job.ResultJson = request.ResultJson;

        if (request.Status.Equals("running", StringComparison.OrdinalIgnoreCase) && job.StartedAt is null)
        {
            job.StartedAt = DateTimeOffset.UtcNow;
        }

        if (request.Status is "succeeded" or "failed" or "cancelled")
        {
            job.CompletedAt = DateTimeOffset.UtcNow;
        }

        if (!string.IsNullOrWhiteSpace(job.AccountId))
        {
            var account = await dbContext.Accounts.FirstOrDefaultAsync(item => item.Id == job.AccountId, cancellationToken);
            if (account is not null)
            {
                if (request.Status == "failed")
                {
                    account.LastFailureAt = DateTimeOffset.UtcNow;
                    account.LastError = request.ErrorMessage;
                }
                else if (request.Status == "succeeded")
                {
                    account.LastActiveAt = DateTimeOffset.UtcNow;
                    account.LastError = null;
                }
            }
        }

        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.Ok(new { jobId = job.Id, status = job.Status });
    }

    private static async Task<IResult> CancelJobAsync(
        Guid jobId,
        CreatorGrowthControlPlaneDbContext dbContext,
        CancellationToken cancellationToken)
    {
        var job = await dbContext.Jobs.FirstOrDefaultAsync(item => item.Id == jobId, cancellationToken);
        if (job is null)
        {
            return Results.NotFound();
        }

        if (job.Status is "succeeded" or "failed" or "cancelled")
        {
            return Results.Ok(new { jobId = job.Id, status = job.Status, unchanged = true });
        }

        job.Status = "cancelled";
        job.CompletedAt = DateTimeOffset.UtcNow;

        dbContext.JobEvents.Add(new JobEventEntity
        {
            JobId = job.Id,
            Level = "warning",
            Step = "cancelled",
            Message = "Cancellation requested from Jobs dashboard."
        });

        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.Ok(new { jobId = job.Id, status = job.Status });
    }

    private static async Task<IResult> AddJobEventAsync(
        Guid jobId,
        JobEventCreateRequest request,
        CreatorGrowthControlPlaneDbContext dbContext,
        CancellationToken cancellationToken)
    {
        var exists = await dbContext.Jobs.AnyAsync(item => item.Id == jobId, cancellationToken);
        if (!exists)
        {
            return Results.NotFound();
        }

        var jobEvent = new JobEventEntity
        {
            JobId = jobId,
            Level = request.Level,
            Step = request.Step,
            Message = request.Message,
            CreatedAt = DateTimeOffset.UtcNow
        };

        dbContext.JobEvents.Add(jobEvent);
        await dbContext.SaveChangesAsync(cancellationToken);

        return Results.Ok(new { eventId = jobEvent.Id });
    }

    private static async Task<IResult> SyncLegacyAsync(LegacyCacheSyncService legacyCacheSyncService, CancellationToken cancellationToken)
    {
        var summary = await legacyCacheSyncService.SyncAsync(cancellationToken);
        return Results.Ok(summary);
    }

    private static string InferProvider(string jobType) => jobType switch
    {
        "youtube_upload" => "youtube",
        "twitter_post" => "twitter",
        "afm_pitch" => "affiliate",
        "outreach_run" => "outreach",
        _ => "system"
    };

    private static string? TrimText(string? text, int maxLength)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return text;
        }

        return text.Length <= maxLength
            ? text
            : $"{text[..maxLength].TrimEnd()}...";
    }
}

