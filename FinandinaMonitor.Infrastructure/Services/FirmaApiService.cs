using System;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using FinandinaMonitor.Domain.Interfaces;
using Microsoft.Extensions.Logging;

namespace FinandinaMonitor.Infrastructure.Services
{
    public class FirmaApiService : IFirmaApiService
    {
        private readonly IHttpClientFactory _httpClientFactory;
        private readonly ILogger<FirmaApiService> _logger;

        public FirmaApiService(IHttpClientFactory httpClientFactory, ILogger<FirmaApiService> logger)
        {
            _httpClientFactory = httpClientFactory;
            _logger = logger;
        }

        public async Task<(bool Success, string? ErrorMessage)> ReprocesarSolicitudAsync(string adicionalJson)
        {
            try
            {
                var client = _httpClientFactory.CreateClient("FirmaApiClient");

                // Enviar el string JSON directamente como StringContent
                var content = new StringContent(adicionalJson, Encoding.UTF8, "application/json");

                // Realiza la petición POST al endpoint especificado
                var response = await client.PostAsync("/api/Management/SingDocuments", content);

                if (response.IsSuccessStatusCode)
                {
                    _logger.LogInformation("Reproceso exitoso mediante Swagger API.");
                    return (true, null);
                }

                var errorMsg = await response.Content.ReadAsStringAsync();
                _logger.LogWarning("Fallo en reproceso Swagger. Estado: {StatusCode}, Error: {Error}",
                    response.StatusCode, errorMsg);
                return (false, $"HTTP {(int)response.StatusCode} {response.StatusCode}: {errorMsg}");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error al consumir la API Swagger de reproceso.");
                return (false, ex.Message);
            }
        }
    }
}
