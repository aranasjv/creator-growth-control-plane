using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace CreatorGrowthControlPlane.Orchestrator.Domain;

[Table("SystemPrompts")]
public sealed class SystemPromptEntity
{
    [Key]
    public Guid Id { get; set; } = Guid.NewGuid();

    [Required]
    [MaxLength(128)]
    public string Key { get; set; } = string.Empty; // e.g., "youtube_topic_generation", "youtube_script_generation"

    [Required]
    [MaxLength(128)]
    public string Description { get; set; } = string.Empty;

    [Required]
    public string PromptText { get; set; } = string.Empty;

    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;
}
