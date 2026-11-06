FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

COPY FinandinaMonitor.sln ./
COPY FinandinaMonitor.Domain/FinandinaMonitor.Domain.csproj FinandinaMonitor.Domain/
COPY FinandinaMonitor.Application/FinandinaMonitor.Application.csproj FinandinaMonitor.Application/
COPY FinandinaMonitor.Infrastructure/FinandinaMonitor.Infrastructure.csproj FinandinaMonitor.Infrastructure/
COPY FinandinaMonitor.UI/FinandinaMonitor.UI.csproj FinandinaMonitor.UI/
RUN dotnet restore FinandinaMonitor.UI/FinandinaMonitor.UI.csproj

COPY FinandinaMonitor.Domain/ FinandinaMonitor.Domain/
COPY FinandinaMonitor.Application/ FinandinaMonitor.Application/
COPY FinandinaMonitor.Infrastructure/ FinandinaMonitor.Infrastructure/
COPY FinandinaMonitor.UI/ FinandinaMonitor.UI/

RUN dotnet publish FinandinaMonitor.UI/FinandinaMonitor.UI.csproj -c Release -o /app/publish --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS final
WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser
USER appuser

COPY --from=build /app/publish .

ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080

ENTRYPOINT ["dotnet", "FinandinaMonitor.UI.dll"]
