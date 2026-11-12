using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using System;
using System.Net.Http;
using System.Security.Claims;
using FinandinaMonitor.Domain.Interfaces;
using FinandinaMonitor.Infrastructure.Data;
using FinandinaMonitor.Infrastructure.Services;
using FinandinaMonitor.Application.Services;

var builder = WebApplication.CreateBuilder(args);

// Configurar servicios de Blazor Web App (.NET 8)
builder.Services.AddRazorComponents()
    .AddInteractiveServerComponents();

// Autenticación por cookie (login opcional vía modal, no se exige al abrir la página).
builder.Services.AddAuthentication(CookieAuthenticationDefaults.AuthenticationScheme)
    .AddCookie(options =>
    {
        options.Cookie.Name = "FinandinaAuth";
        options.LoginPath = "/";
        options.AccessDeniedPath = "/";
        options.ExpireTimeSpan = TimeSpan.FromHours(8);
        options.SlidingExpiration = true;
    });
builder.Services.AddAuthorization();
builder.Services.AddCascadingAuthenticationState();

// Registrar dependencias de la arquitectura limpia
builder.Services.AddScoped<ISolicitudRepository, SolicitudRepository>();
builder.Services.AddScoped<IBiometriaRepository, BiometriaRepository>();
builder.Services.AddScoped<IUsuarioRepository, UsuarioRepository>();
builder.Services.AddScoped<IFirmaApiService, FirmaApiService>();
builder.Services.AddScoped<ILogApiService, LogApiService>();
builder.Services.AddScoped<IReprocesoAvanzadoApiService, ReprocesoAvanzadoApiService>();
builder.Services.AddScoped<ReprocesoApplicationService>();

// Histórico de reprocesos: almacén en memoria compartido + verificación en segundo plano (5 min después)
builder.Services.AddSingleton<IHistoricoReprocesoStore, HistoricoReprocesoStore>();
builder.Services.AddHostedService<HistoricoVerificacionBackgroundService>();

// Alertas de monitoreo temporales (Buscador): almacén en memoria compartido + evaluación en segundo plano
builder.Services.AddSingleton<IAlertaMonitoreoStore, AlertaMonitoreoStore>();
builder.Services.AddHostedService<AlertaMonitoreoBackgroundService>();

// Timeout generoso: alguna de estas APIs puede tardar varios minutos en responder
var apiClientTimeout = TimeSpan.FromMinutes(3);

// Configurar HttpClientFactory ignorando errores de certificados SSL autofirmados
builder.Services.AddHttpClient("FirmaApiClient", client =>
{
    var baseUrl = builder.Configuration["FirmaApi:BaseUrl"] ?? "https://10.240.1.117:4023";
    client.BaseAddress = new Uri(baseUrl);
    client.Timeout = apiClientTimeout;
})
.ConfigurePrimaryHttpMessageHandler(() => new HttpClientHandler
{
    ServerCertificateCustomValidationCallback = (message, cert, chain, errors) => true
});

// API de Management (puerto 4023) usada para ReprocessCases
builder.Services.AddHttpClient("ReprocessApiClient", client =>
{
    var baseUrl = builder.Configuration["ReprocessApi:BaseUrl"] ?? "https://10.240.1.117:4023";
    client.BaseAddress = new Uri(baseUrl);
    client.Timeout = apiClientTimeout;
})
.ConfigurePrimaryHttpMessageHandler(() => new HttpClientHandler
{
    ServerCertificateCustomValidationCallback = (message, cert, chain, errors) => true
});

// API de Signature (puerto 4022) usada para Save y UpdateState
builder.Services.AddHttpClient("SignatureApiClient", client =>
{
    var baseUrl = builder.Configuration["SignatureApi:BaseUrl"] ?? "https://10.240.1.117:4022";
    client.BaseAddress = new Uri(baseUrl);
    client.Timeout = apiClientTimeout;
})
.ConfigurePrimaryHttpMessageHandler(() => new HttpClientHandler
{
    ServerCertificateCustomValidationCallback = (message, cert, chain, errors) => true
});

// Health check para Docker / monitoreo
builder.Services.AddHealthChecks();

var app = builder.Build();

using (var scope = app.Services.CreateScope())
{
    var usuarioRepository = scope.ServiceProvider.GetRequiredService<IUsuarioRepository>();
    await usuarioRepository.InicializarAsync();
}

// Configurar el pipeline HTTP
if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error", createScopeForErrors: true);
    app.UseHsts();
}

app.UseHttpsRedirection();
app.UseStaticFiles();
app.UseAuthentication();
app.UseAuthorization();
app.UseAntiforgery();

app.MapHealthChecks("/healthz");

// Login/Logout vía POST de formulario normal (no Blazor): dispara un reload de página completo
// para que el circuito de Blazor arranque de nuevo ya con la cookie de autenticación presente.
app.MapPost("/Account/Login", async (HttpContext http, IUsuarioRepository usuarios, [FromForm] string username, [FromForm] string password, [FromForm] string? returnUrl) =>
{
    // returnUrl puede venir con un ?loginError=1 de un intento previo: se descarta la query
    // para no ir acumulando parámetros en la URL en intentos fallidos sucesivos.
    var returnPath = string.IsNullOrWhiteSpace(returnUrl) ? "/" : returnUrl.Split('?')[0];

    var usuario = await usuarios.ValidarCredencialesAsync(username, password);
    if (usuario is null)
    {
        return Results.Redirect($"{returnPath}?loginError=1");
    }

    var claims = new[]
    {
        new Claim(ClaimTypes.Name, usuario.Username),
        new Claim("EsAdmin", usuario.EsAdmin.ToString()),
        new Claim("PuedeBorrar", usuario.PuedeBorrar.ToString()),
        new Claim("PuedeReprocesar", usuario.PuedeReprocesar.ToString()),
        new Claim("PuedeVerCompleto", usuario.PuedeVerCompleto.ToString())
    };
    var identity = new ClaimsIdentity(claims, CookieAuthenticationDefaults.AuthenticationScheme);
    await http.SignInAsync(CookieAuthenticationDefaults.AuthenticationScheme, new ClaimsPrincipal(identity));

    return Results.Redirect(returnPath);
}).DisableAntiforgery();

app.MapPost("/Account/Logout", async (HttpContext http) =>
{
    await http.SignOutAsync(CookieAuthenticationDefaults.AuthenticationScheme);
    return Results.Redirect("/");
}).DisableAntiforgery();

app.MapStaticAssets();
app.MapRazorComponents<FinandinaMonitor.UI.Components.App>()
    .AddInteractiveServerRenderMode();

app.Run();
