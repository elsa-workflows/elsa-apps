# Build stage
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src

# Copy project file and restore dependencies
COPY ["Elsa.Server.Studio.BlazorWasm.csproj", "./"]
RUN dotnet restore "Elsa.Server.Studio.BlazorWasm.csproj"

# Copy source code and build
COPY . .
RUN dotnet build "Elsa.Server.Studio.BlazorWasm.csproj" -c Release -o /app/build

# Publish stage
FROM build AS publish
RUN dotnet publish "Elsa.Server.Studio.BlazorWasm.csproj" -c Release -o /app/publish /p:UseAppHost=false

# Runtime stage
FROM mcr.microsoft.com/dotnet/aspnet:9.0 AS final
WORKDIR /app
EXPOSE 80
COPY --from=publish /app/publish .

ENTRYPOINT ["dotnet", "Elsa.Server.Studio.BlazorWasm.dll"]