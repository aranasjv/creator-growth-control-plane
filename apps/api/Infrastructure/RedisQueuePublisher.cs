using System.Text.Json;
using StackExchange.Redis;

namespace CreatorGrowthControlPlane.Orchestrator.Infrastructure;

public sealed class RedisQueuePublisher(IConnectionMultiplexer redis, IConfiguration configuration)
{
    public async Task EnqueueAsync(object payload)
    {
        var queueName = configuration["Platform:QueueName"] ?? "cgcp:jobs";
        var db = redis.GetDatabase();
        await db.ListRightPushAsync(queueName, JsonSerializer.Serialize(payload));
    }
}

