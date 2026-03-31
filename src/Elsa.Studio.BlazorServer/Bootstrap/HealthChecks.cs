using Elsa.Studio.BlazorServer.Helpers;
using HealthChecks.UI.Client;
using Shared.Constants;
using HealthCheckOptions = Shared.Options.HealthCheckOptions;

namespace Elsa.Studio.BlazorServer.Bootstrap
{
    public static class HealthChecks
    {
        public static IServiceCollection ConfigureHealthChecks(this IServiceCollection services, IConfiguration configuration)
        {
            var healthCheckOptions = configuration.GetOptionsOrDefault<HealthCheckOptions>(SettingKeys.HealthChecks);

            if (healthCheckOptions is not null && !healthCheckOptions.Disabled)
                services.AddHealthChecks();

            return services;
        }

        public static void ConfigureHealthCheckEndpoints(this WebApplication app)
        {
            var healthCheckOptions = app.Configuration.GetOptionsOrDefault<HealthCheckOptions>(SettingKeys.HealthChecks);

            if (healthCheckOptions is null || healthCheckOptions.Disabled)
                return;

            app.MapHealthChecks("/health/ready", new()
            {
                Predicate = check => check.Tags.Contains("ready"),
                ResponseWriter = UIResponseWriter.WriteHealthCheckUIResponse
            });

            app.MapHealthChecks("/health/live", new()
            {
                Predicate = check => check.Tags.Contains("live"),
                ResponseWriter = UIResponseWriter.WriteHealthCheckUIResponse
            });

            app.MapHealthChecks("/health/start", new()
            {
                Predicate = check => check.Tags.Contains("start"),
                ResponseWriter = UIResponseWriter.WriteHealthCheckUIResponse
            });
        }
    }
}
