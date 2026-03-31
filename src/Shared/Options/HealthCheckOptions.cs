namespace Shared.Options
{
    public sealed class HealthCheckOptions
    {
        public bool DisableStart { get; set; }

        public bool DisableLive { get; set; }

        public bool DisableReady { get; set; }

        public bool Disabled => DisableReady && DisableStart && DisableLive;
    }
}
