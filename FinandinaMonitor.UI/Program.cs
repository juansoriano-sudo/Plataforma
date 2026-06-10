using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using System;
using System.Net.Http;
using FinandinaMonitor.Domain.Interfaces;
using FinandinaMonitor.Infrastructure.Data;
using FinandinaMonitor.Infrastructure.Services;
using FinandinaMonitor.Application.Services;

var builder = WebApplication.CreateBuilder(args);

// Configurar servicios de Blazor Web App (.NET 8)
builder.Services.AddRazorComponents()
    .AddInteractiveServerComponents();

// Registrar dependencias de la arquitectura limpia
builder.Services.AddScoped<ISolicitudRepository, SolicitudRepository>();
builder.Services.AddScoped<IFirmaApiService, FirmaApiService>();
builder.Services.AddScoped<ILogApiService, LogApiService>();
builder.Services.AddScoped<ReprocesoApplicationService>();

// Configurar HttpClientFactory ignorando errores de certificados SSL autofirmados
builder.Services.AddHttpClient("FirmaApiClient", client =>
{
    var baseUrl = builder.Configuration["FirmaApi:BaseUrl"] ?? "https://10.240.1.117:4023";
    client.BaseAddress = new Uri(baseUrl);
})
.ConfigurePrimaryHttpMessageHandler(() => new HttpClientHandler
{
    ServerCertificateCustomValidationCallback = (message, cert, chain, errors) => true
});

builder.Services.AddHttpClient("LogApiClient", client =>
{
    var baseUrl = builder.Configuration["LogApi:BaseUrl"] ?? "http://localhost:5005";
    client.BaseAddress = new Uri(baseUrl);
});

var app = builder.Build();

// Configurar el pipeline HTTP
if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error", createScopeForErrors: true);
    app.UseHsts();
}

app.UseHttpsRedirection();
app.UseStaticFiles();
app.UseAntiforgery();

app.MapRazorComponents<FinandinaMonitor.UI.Components.App>()
    .AddInteractiveServerRenderMode();

app.Run();
