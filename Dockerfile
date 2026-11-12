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

RUN dotnet publish FinandinaMonitor.UI/FinandinaMonitor.UI.csproj -c Release -o /app/publish

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS final
WORKDIR /app

# curl: usado por el HEALTHCHECK. tzdata: zona horaria America/Bogota.
# gss-ntlmssp: permite autenticar con SQL Server por NTLM (Integrated Security) en Linux
# mientras el DBA crea el login dedicado (ver scripts/create-motorfirma-login.sql y README).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl tzdata gss-ntlmssp \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=America/Bogota

RUN mkdir -p /https \
    && chown -R app:app /app /https
USER app

COPY --from=build /app/publish .

# HTTPS directo en Kestrel (mismo certificado de desarrollo que ya usan los usuarios).
# La ruta/clave del .pfx y NTLM_USER_FILE se inyectan vía docker-compose (env_file / volumes).
ENV ASPNETCORE_URLS=https://+:8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -k -f https://localhost:8080/healthz || exit 1

ENTRYPOINT ["dotnet", "FinandinaMonitor.UI.dll"]
