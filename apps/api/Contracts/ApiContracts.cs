namespace CreatorGrowthControlPlane.Orchestrator.Contracts;

public sealed record CreateJobRequest(
    string Type,
    string? Provider,
    string? AccountId,
    string? ProductId,
    string? Model,
    Dictionary<string, string?>? Parameters);

public sealed record JobStatusUpdateRequest(
    string Status,
    string? ErrorMessage,
    string? ResultJson);

public sealed record JobEventCreateRequest(
    string Level,
    string Step,
    string Message);

public sealed record SyncLegacyCacheResponse(
    int AccountsImported,
    int AssetsImported,
    int ProductsImported);

