# Build stage
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# Copy project file and restore dependencies
COPY ["Elsa.Studio.BlazorServer.csproj", "./"]
RUN dotnet restore "Elsa.Studio.BlazorServer.csproj"

# Copy source code and build
COPY . .
RUN dotnet build "Elsa.Studio.BlazorServer.csproj" -c Release -o /app/build

# Publish stage
FROM build AS publish
RUN dotnet publish "Elsa.Studio.BlazorServer.csproj" -c Release -o /app/publish /p:UseAppHost=false

# Runtime stage
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final
WORKDIR /app
EXPOSE 80
COPY --from=publish /app/publish .

ENTRYPOINT ["dotnet", "Elsa.Studio.BlazorServer.dll"]