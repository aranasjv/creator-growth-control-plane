using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace CreatorGrowthControlPlane.Orchestrator.Domain;

[Table("GlobalSettings")]
public sealed class GlobalSettingsEntity
{
    [Key]
    public Guid Id { get; set; } = Guid.NewGuid();

    [MaxLength(256)]
    public string? OpenAIApiKey { get; set; }

    [MaxLength(256)]
    public string? GeminiApiKey { get; set; }

    [MaxLength(64)]
    public string ActiveModelProvider { get; set; } = "ollama"; // "ollama", "openai", "gemini"

    [MaxLength(128)]
    public string OllamaModelName { get; set; } = "llama3";
}
