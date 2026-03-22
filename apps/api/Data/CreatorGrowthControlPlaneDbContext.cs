using CreatorGrowthControlPlane.Orchestrator.Domain;
using Microsoft.EntityFrameworkCore;

namespace CreatorGrowthControlPlane.Orchestrator.Data;

public sealed class CreatorGrowthControlPlaneDbContext(DbContextOptions<CreatorGrowthControlPlaneDbContext> options) : DbContext(options)
{
    public DbSet<AccountEntity> Accounts => Set<AccountEntity>();
    public DbSet<JobEntity> Jobs => Set<JobEntity>();
    public DbSet<JobEventEntity> JobEvents => Set<JobEventEntity>();
    public DbSet<ContentAssetEntity> ContentAssets => Set<ContentAssetEntity>();
    public DbSet<AffiliateProductEntity> AffiliateProducts => Set<AffiliateProductEntity>();
    public DbSet<RevenueRecordEntity> RevenueRecords => Set<RevenueRecordEntity>();
    public DbSet<CostLedgerEntryEntity> CostLedgerEntries => Set<CostLedgerEntryEntity>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<AccountEntity>().HasKey(account => account.Id);
        modelBuilder.Entity<AccountEntity>().Property(account => account.Provider).HasMaxLength(32);
        modelBuilder.Entity<AccountEntity>().Property(account => account.Nickname).HasMaxLength(128);

        modelBuilder.Entity<JobEntity>().HasKey(job => job.Id);
        modelBuilder.Entity<JobEntity>().Property(job => job.Type).HasMaxLength(64);
        modelBuilder.Entity<JobEntity>().Property(job => job.Status).HasMaxLength(32);
        modelBuilder.Entity<JobEntity>().Property(job => job.Provider).HasMaxLength(32);
        modelBuilder.Entity<JobEntity>()
            .HasOne(job => job.Account)
            .WithMany(account => account.Jobs)
            .HasForeignKey(job => job.AccountId)
            .OnDelete(DeleteBehavior.SetNull);
        modelBuilder.Entity<JobEntity>().HasIndex(job => job.CreatedAt);
        modelBuilder.Entity<JobEntity>().HasIndex(job => job.Status);

        modelBuilder.Entity<JobEventEntity>().HasKey(jobEvent => jobEvent.Id);
        modelBuilder.Entity<JobEventEntity>()
            .HasOne(jobEvent => jobEvent.Job)
            .WithMany(job => job.Events)
            .HasForeignKey(jobEvent => jobEvent.JobId)
            .OnDelete(DeleteBehavior.Cascade);
        modelBuilder.Entity<JobEventEntity>().HasIndex(jobEvent => new { jobEvent.JobId, jobEvent.CreatedAt });

        modelBuilder.Entity<ContentAssetEntity>().HasKey(asset => asset.Id);
        modelBuilder.Entity<ContentAssetEntity>().HasIndex(asset => asset.SourceId).IsUnique();
        modelBuilder.Entity<ContentAssetEntity>()
            .HasOne(asset => asset.Account)
            .WithMany(account => account.Assets)
            .HasForeignKey(asset => asset.AccountId)
            .OnDelete(DeleteBehavior.Cascade);
        modelBuilder.Entity<ContentAssetEntity>().Property(asset => asset.Revenue).HasPrecision(18, 2);
        modelBuilder.Entity<ContentAssetEntity>().Property(asset => asset.Cost).HasPrecision(18, 2);

        modelBuilder.Entity<AffiliateProductEntity>().HasKey(product => product.Id);
        modelBuilder.Entity<AffiliateProductEntity>().HasIndex(product => product.AffiliateLink);

        modelBuilder.Entity<RevenueRecordEntity>().HasKey(record => record.Id);
        modelBuilder.Entity<RevenueRecordEntity>().Property(record => record.Amount).HasPrecision(18, 2);
        modelBuilder.Entity<RevenueRecordEntity>().HasIndex(record => record.OccurredAt);

        modelBuilder.Entity<CostLedgerEntryEntity>().HasKey(entry => entry.Id);
        modelBuilder.Entity<CostLedgerEntryEntity>().Property(entry => entry.Amount).HasPrecision(18, 2);
        modelBuilder.Entity<CostLedgerEntryEntity>().HasIndex(entry => entry.OccurredAt);
    }
}

