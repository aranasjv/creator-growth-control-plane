using System.Text.Json;
using CreatorGrowthControlPlane.Orchestrator.Data;
using CreatorGrowthControlPlane.Orchestrator.Endpoints;
using CreatorGrowthControlPlane.Orchestrator.Infrastructure;
using CreatorGrowthControlPlane.Orchestrator.Services;
using Microsoft.EntityFrameworkCore;
using MongoDB.Bson;
using MongoDB.Driver;
using StackExchange.Redis;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddProblemDetails();
builder.Services.AddEndpointsApiExplorer();
builder.Services.ConfigureHttpJsonOptions(options =>
{
    options.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;
});

builder.Services.AddCors(options =>
{
    options.AddPolicy("dashboard", policy =>
    {
        var origins = builder.Configuration.GetSection("Platform:AllowedOrigins").Get<string[]>() ?? ["http://localhost:3000"];
        policy.WithOrigins(origins).AllowAnyHeader().AllowAnyMethod();
    });
});

builder.Services.AddDbContext<CreatorGrowthControlPlaneDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("Postgres")));

builder.Services.AddSingleton<IConnectionMultiplexer>(_ =>
    ConnectionMultiplexer.Connect(builder.Configuration.GetConnectionString("Redis") ?? "localhost:6379"));
builder.Services.AddSingleton<IMongoClient>(_ =>
    new MongoClient(builder.Configuration.GetConnectionString("Mongo") ?? "mongodb://localhost:27017"));

builder.Services.AddScoped<RedisQueuePublisher>();
builder.Services.AddScoped<LegacyCacheSyncService>();

var app = builder.Build();

app.UseExceptionHandler();
app.UseCors("dashboard");

app.MapGet("/health", async (CreatorGrowthControlPlaneDbContext db, IConnectionMultiplexer redis, IMongoClient mongo, CancellationToken cancellationToken) =>
{
    var postgres = await db.Database.CanConnectAsync(cancellationToken);
    var redisLatency = await redis.GetDatabase().PingAsync();
    var mongoHealthy = false;

    try
    {
        var pingResult = await mongo.GetDatabase("admin").RunCommandAsync<BsonDocument>(
            new BsonDocument("ping", 1),
            cancellationToken: cancellationToken);
        mongoHealthy = pingResult.TryGetValue("ok", out var okValue) && okValue.ToDouble() >= 1;
    }
    catch
    {
        mongoHealthy = false;
    }

    return Results.Ok(new
    {
        status = postgres && mongoHealthy ? "ok" : "degraded",
        checks = new
        {
            postgres,
            redis = redisLatency.TotalMilliseconds >= 0,
            redisLatencyMs = redisLatency.TotalMilliseconds,
            mongo = mongoHealthy
        }
    });
});

app.MapJobEndpoints();
app.MapDashboardEndpoints();
app.MapSettingsEndpoints();
app.MapSystemPromptEndpoints();

await using (var scope = app.Services.CreateAsyncScope())
{
    var db = scope.ServiceProvider.GetRequiredService<CreatorGrowthControlPlaneDbContext>();
    await db.Database.EnsureCreatedAsync();
    await db.Database.ExecuteSqlRawAsync(
        @"ALTER TABLE ""GlobalSettings""
          ADD COLUMN IF NOT EXISTS ""OpenAIModelName"" character varying(128) NOT NULL DEFAULT 'gpt-4o-mini';");
    await db.Database.ExecuteSqlRawAsync(
        @"ALTER TABLE ""GlobalSettings""
          ADD COLUMN IF NOT EXISTS ""GeminiModelName"" character varying(128) NOT NULL DEFAULT 'gemini-2.5-flash';");

    var legacySync = scope.ServiceProvider.GetRequiredService<LegacyCacheSyncService>();
    await legacySync.SyncAsync();
}

app.Run();

