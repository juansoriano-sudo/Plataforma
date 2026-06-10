using System;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;
using FinandinaMonitor.Domain.Interfaces;
using Microsoft.Extensions.Logging;

namespace FinandinaMonitor.Infrastructure.Services
{
    public class LogApiService : ILogApiService
    {
        private readonly IHttpClientFactory _httpClientFactory;
        private readonly ILogger<LogApiService> _logger;

        public LogApiService(IHttpClientFactory httpClientFactory, ILogger<LogApiService> logger)
        {
            _httpClientFactory = httpClientFactory;
            _logger = logger;
        }

        public async Task<(bool IsConnected, string Message)> CheckHealthAsync()
        {
            try
            {
                var client = _httpClientFactory.CreateClient("LogApiClient");
                var response = await client.GetAsync("/health");

                if (response.IsSuccessStatusCode)
                {
                    return (true, "Conectado");
                }

                var content = await response.Content.ReadAsStringAsync();
                using var document = JsonDocument.Parse(content);
                var root = document.RootElement;
                
                if (root.TryGetProperty("db", out var dbError))
                {
                    return (false, dbError.GetString() ?? "Error desconocido en BD MariaDB");
                }

                return (false, $"Estado HTTP {response.StatusCode}");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error al conectar con la API de Logs");
                return (false, "La API local de Python (Puerto 5005) parece estar apagada o inaccesible.");
            }
        }

        public async Task<(bool Success, string? Adicional, string? ErrorMessage)> GetAdicionalAsync(long idSolicitud)
        {
            try
            {
                var client = _httpClientFactory.CreateClient("LogApiClient");
                var response = await client.GetAsync($"/query?idSolicitud={idSolicitud}");

                if (!response.IsSuccessStatusCode)
                {
                    return (false, null, $"Fallo HTTP {response.StatusCode}");
                }

                var content = await response.Content.ReadAsStringAsync();
                
                // Parse the JSON response
                using var document = JsonDocument.Parse(content);
                var root = document.RootElement;

                // Check for errors in the response payload
                if (root.TryGetProperty("error", out var errorProp) && 
                    errorProp.ValueKind == JsonValueKind.String && 
                    !string.IsNullOrWhiteSpace(errorProp.GetString()))
                {
                    return (false, null, errorProp.GetString());
                }

                // Extract the "Adicional" value
                if (root.TryGetProperty("Adicional", out var adicionalProp))
                {
                    if (adicionalProp.ValueKind == JsonValueKind.String)
                    {
                        var value = adicionalProp.GetString();
                        if (!string.IsNullOrWhiteSpace(value))
                        {
                            return (true, value, null);
                        }
                        return (false, null, "La propiedad Adicional está vacía o es nula");
                    }
                    else
                    {
                        return (true, adicionalProp.GetRawText(), null);
                    }
                }

                return (false, null, "Respuesta exitosa, pero no se encontró la columna 'Adicional'");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Excepción al consultar API local de MariaDB para {IdSolicitud}.", idSolicitud);
                return (false, null, "Excepción interna del cliente HTTP");
            }
        }
    }
}
