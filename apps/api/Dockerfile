FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

COPY ["apps/api/CreatorGrowthControlPlane.Orchestrator.csproj", "apps/api/"]
RUN dotnet restore "apps/api/CreatorGrowthControlPlane.Orchestrator.csproj"

COPY ["apps/api/", "apps/api/"]
RUN dotnet publish "apps/api/CreatorGrowthControlPlane.Orchestrator.csproj" -c Release -o /app/publish /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS final
WORKDIR /app

ENV ASPNETCORE_URLS=http://0.0.0.0:8080
EXPOSE 8080

COPY --from=build /app/publish .

ENTRYPOINT ["dotnet", "CreatorGrowthControlPlane.Orchestrator.dll"]

