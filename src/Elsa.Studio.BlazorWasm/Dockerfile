# Build stage
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src

# Copy project and config files
COPY Directory.Build.props ../../Directory.Build.props
COPY Directory.Packages.props ../../Directory.Packages.props
COPY NuGet.Config ../../NuGet.Config
COPY src/Elsa.Studio.BlazorWasm/Elsa.Studio.BlazorWasm.csproj ./

# Restore dependencies
RUN dotnet restore "Elsa.Studio.BlazorWasm.csproj"

# Copy the rest of the source code
COPY src/Elsa.Studio.BlazorWasm/. ./

# Build the project
RUN dotnet build "Elsa.Studio.BlazorWasm.csproj" -c Release -o /app/build

# Publish stage
FROM build AS publish
RUN dotnet publish "Elsa.Studio.BlazorWasm.csproj" -c Release -o /app/publish /p:UseAppHost=false

# NGINX stage
FROM nginx:alpine AS final
COPY src/Elsa.Studio.BlazorWasm/nginx.conf /etc/nginx/nginx.conf
COPY --from=publish /app/publish/wwwroot /usr/share/nginx/html
EXPOSE 80

