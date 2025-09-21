# Build stage
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src

# Copy project and config files
COPY Directory.Build.props ../../Directory.Build.props
COPY Directory.Packages.props ../../Directory.Packages.props
COPY NuGet.Config ../../NuGet.Config
COPY src/Elsa.Studio.BlazorServer/Elsa.Studio.BlazorServer.csproj ./
COPY src/Elsa.Server.Shared/Elsa.Server.Shared.csproj ../Elsa.Server.Shared/

# Restore dependencies
RUN dotnet restore "Elsa.Studio.BlazorServer.csproj"

# Copy all project files before build (for multi-project references)
COPY src/**/*.csproj ../

# Copy the rest of the source code
COPY src/Elsa.Studio.BlazorServer/. ./
COPY src/Elsa.Server.Shared/. ../Elsa.Server.Shared/

# Build the project
RUN dotnet build "Elsa.Studio.BlazorServer.csproj" -c Release -o /app/build

# Publish stage
FROM build AS publish
RUN dotnet publish "Elsa.Studio.BlazorServer.csproj" -c Release -o /app/publish /p:UseAppHost=false

# Runtime stage
FROM mcr.microsoft.com/dotnet/aspnet:9.0 AS final
WORKDIR /app
EXPOSE 80
COPY --from=publish /app/publish .

ENTRYPOINT ["dotnet", "Elsa.Studio.BlazorServer.dll"]