using Elsa.Studio.Localization.Time;
using Elsa.Studio.Localization.Time.Providers;
using Elsa.Studio.BlazorServer.Bootstrap;

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseStaticWebAssets();

var services = builder.Services;
var configuration = builder.Configuration;

services.SetupCore(configuration);
var backendApiConfig = services.ConfigureBackend(configuration);
services.AddModules(configuration, backendApiConfig);
services.ConfigureLogin(configuration);
services.ConfigureDiagnostics(configuration);
services.ConfigureHealthChecks(configuration);

services.AddScoped<ITimeZoneProvider, LocalTimeZoneProvider>();
var app = builder.Build();

if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error");
    app.UseHsts();
}

app.ConfigureHealthCheckEndpoints();

app.UseHttpsRedirection();
app.UseRouting();
app.UseStaticFiles();
app.UseAuthentication();
app.UseAuthorization();
app.MapRazorPages();
app.MapBlazorHub();
app.MapFallbackToPage("/_Host");

app.Run();