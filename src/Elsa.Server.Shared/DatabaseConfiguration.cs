using Elsa.EntityFrameworkCore;
using Elsa.EntityFrameworkCore.Extensions;
using Microsoft.Extensions.Configuration;

namespace Elsa.Server.Shared;

public static class DatabaseConfiguration
{
    public static void ConfigureEntityFrameworkCore<TFeature, TDbContext>(PersistenceFeatureBase<TFeature, TDbContext> ef, IConfiguration configuration) where TDbContext : ElsaDbContextBase where TFeature : PersistenceFeatureBase<TFeature, TDbContext>
    {
        var dbProvider = configuration.GetValue<string>("DatabaseProvider") ?? "Sqlite";
        var connectionString = configuration.GetConnectionString(dbProvider) ?? "Data Source=elsa.db;Cache=Shared";
        
        switch (dbProvider)
        {
            case "Sqlite":
                ef.UseSqlite(connectionString);
                break;
            case "SqlServer":
                ef.UseSqlServer(connectionString);
                break;
            case "PostgreSql":
                ef.UsePostgreSql(connectionString);
                break;
            case "MySql":
                ef.UseMySql(connectionString);
                break;
            case "Oracle":
                ef.UseOracle(connectionString);
                break;
            default:
                throw new NotSupportedException($"Database provider '{dbProvider}' is not supported.");
        }
    }
}