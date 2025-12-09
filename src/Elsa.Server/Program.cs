using Elsa.Agents;
using Elsa.Extensions;
using Elsa.Persistence.EFCore.Modules.Management;
using Elsa.Persistence.EFCore.Modules.Runtime;
using static Elsa.Server.Shared.DatabaseConfiguration;

var builder = WebApplication.CreateBuilder(args);
var services = builder.Services;
var configuration = builder.Configuration;

services.AddElsa(elsa =>
{
    elsa.UseWorkflowManagement(management => management.UseEntityFrameworkCore(ef => ConfigureEntityFrameworkCore(ef, configuration)))
        .UseWorkflowRuntime(runtime => runtime.UseEntityFrameworkCore(ef => ConfigureEntityFrameworkCore(ef, configuration)))
        .UseIdentity(identity =>
        {
            identity.TokenOptions = options => configuration.Bind("Identity:Tokens", options);
            identity.UseAdminUserProvider();
        })
        .UseDefaultAuthentication(auth => auth.UseAdminApiKey())
        .UseWorkflowsApi()
        .UseCSharp()
        .UseJavaScript(options => options.AllowClrAccess = true)
        .UseHttp(options => options.ConfigureHttpOptions = httpOptions => configuration.Bind("Http", httpOptions))
        .UseScheduling()
        .UseAgentActivities()
        .UseAgentPersistence(persistence => persistence.UseEntityFrameworkCore(ef => ConfigureEntityFrameworkCoreForAgents(ef, configuration)))
        .UseAgentsApi()
        .AddActivitiesFrom<Program>()
        .AddWorkflowsFrom<Program>();
});

builder.Services.AddCors(cors => cors
    .AddDefaultPolicy(policy => policy
        .AllowAnyOrigin() // For demo purposes only. Use a specific origin instead.
        .AllowAnyHeader()
        .AllowAnyMethod()
        .WithExposedHeaders("x-elsa-workflow-instance-id"))); // Required for Elsa Studio in order to support running workflows from the designer. Alternatively, you can use the `*` wildcard to expose all headers.

builder.Services.AddHealthChecks();

var app = builder.Build();

app.MapHealthChecks("/");
app.UseCors();
app.UseAuthentication();
app.UseAuthorization();
app.UseWorkflowsApi();
app.UseWorkflows();

app.Run();