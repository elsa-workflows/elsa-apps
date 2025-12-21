# Build stage
FROM --platform=$BUILDPLATFORM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

# Copy project and config files
COPY Directory.Build.props ../../Directory.Build.props
COPY Directory.Packages.props ../../Directory.Packages.props
COPY NuGet.Config ../../NuGet.Config
COPY src/Elsa.Studio.BlazorWasm/Elsa.Server.Studio.BlazorWasm.csproj ./

# Restore dependencies
RUN dotnet restore "Elsa.Studio.BlazorWasm.csproj"

# Copy all project files before build (for multi-project references)
COPY src/**/*.csproj ../

# Copy the rest of the source code
COPY src/Elsa.Studio.BlazorWasm/. ./

# Build the project
RUN dotnet build "Elsa.Studio.BlazorWasm.csproj" -c Release -o /app/build

# Publish stage
FROM build AS publish
RUN dotnet publish "Elsa.Studio.BlazorWasm.csproj" -c Release -o /app/publish /p:UseAppHost=false

# Runtime stage
FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS final
WORKDIR /app
EXPOSE 8080
COPY --from=publish /app/publish .

ENTRYPOINT ["dotnet", "Elsa.Studio.BlazorWasm.dll"]