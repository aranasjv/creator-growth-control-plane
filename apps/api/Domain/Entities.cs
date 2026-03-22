namespace CreatorGrowthControlPlane.Orchestrator.Domain;

public sealed class AccountEntity
{
    public string Id { get; set; } = string.Empty;
    public string Provider { get; set; } = string.Empty;
    public string Nickname { get; set; } = string.Empty;
    public string? Topic { get; set; }
    public string? Niche { get; set; }
    public string? Language { get; set; }
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
    public DateTimeOffset? LastActiveAt { get; set; }
    public DateTimeOffset? LastFailureAt { get; set; }
    public string? LastError { get; set; }

    public ICollection<JobEntity> Jobs { get; set; } = new List<JobEntity>();
    public ICollection<ContentAssetEntity> Assets { get; set; } = new List<ContentAssetEntity>();
}

public sealed class JobEntity
{
    public Guid Id { get; set; }
    public string Type { get; set; } = string.Empty;
    public string Status { get; set; } = string.Empty;
    public string Provider { get; set; } = string.Empty;
    public string? AccountId { get; set; }
    public string? ProductId { get; set; }
    public string? Model { get; set; }
    public string? PayloadJson { get; set; }
    public string? ResultJson { get; set; }
    public string? ErrorMessage { get; set; }
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
    public DateTimeOffset? StartedAt { get; set; }
    public DateTimeOffset? CompletedAt { get; set; }

    public AccountEntity? Account { get; set; }
    public ICollection<JobEventEntity> Events { get; set; } = new List<JobEventEntity>();
}

public sealed class JobEventEntity
{
    public long Id { get; set; }
    public Guid JobId { get; set; }
    public string Level { get; set; } = string.Empty;
    public string Step { get; set; } = string.Empty;
    public string Message { get; set; } = string.Empty;
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;

    public JobEntity Job { get; set; } = null!;
}

public sealed class ContentAssetEntity
{
    public Guid Id { get; set; }
    public string Kind { get; set; } = string.Empty;
    public string Provider { get; set; } = string.Empty;
    public string SourceId { get; set; } = string.Empty;
    public string AccountId { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public string? Description { get; set; }
    public string? Url { get; set; }
    public string? LocalPath { get; set; }
    public int? Views { get; set; }
    public int? Clicks { get; set; }
    public decimal? Revenue { get; set; }
    public decimal? Cost { get; set; }
    public DateTimeOffset PublishedAt { get; set; } = DateTimeOffset.UtcNow;

    public AccountEntity Account { get; set; } = null!;
}

public sealed class AffiliateProductEntity
{
    public string Id { get; set; } = string.Empty;
    public string AffiliateLink { get; set; } = string.Empty;
    public string? AccountId { get; set; }
    public string? AccountNickname { get; set; }
    public string? Name { get; set; }
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}

public sealed class RevenueRecordEntity
{
    public Guid Id { get; set; }
    public string Source { get; set; } = string.Empty;
    public string? ProductId { get; set; }
    public decimal Amount { get; set; }
    public string Currency { get; set; } = "USD";
    public int? Clicks { get; set; }
    public int? Conversions { get; set; }
    public string? Notes { get; set; }
    public DateTimeOffset OccurredAt { get; set; } = DateTimeOffset.UtcNow;
}

public sealed class CostLedgerEntryEntity
{
    public Guid Id { get; set; }
    public Guid? JobId { get; set; }
    public string Category { get; set; } = string.Empty;
    public decimal Amount { get; set; }
    public string Currency { get; set; } = "USD";
    public string? Notes { get; set; }
    public DateTimeOffset OccurredAt { get; set; } = DateTimeOffset.UtcNow;
}

