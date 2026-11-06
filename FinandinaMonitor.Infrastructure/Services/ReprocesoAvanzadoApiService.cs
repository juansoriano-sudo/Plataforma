using System;
using System.Net.Http;
using System.Net.Http.Json;
using System.Threading.Tasks;
using FinandinaMonitor.Domain.Interfaces;
using Microsoft.Extensions.Logging;

namespace FinandinaMonitor.Infrastructure.Services
{
    public class ReprocesoAvanzadoApiService : IReprocesoAvanzadoApiService
    {
        private readonly IHttpClientFactory _httpClientFactory;
        private readonly ILogger<ReprocesoAvanzadoApiService> _logger;

        public ReprocesoAvanzadoApiService(IHttpClientFactory httpClientFactory, ILogger<ReprocesoAvanzadoApiService> logger)
        {
            _httpClientFactory = httpClientFactory;
            _logger = logger;
        }

        public async Task<(bool Success, string? ErrorMessage)> ReprocessCasesAsync(string radNumber, bool isCrossSelling)
        {
            try
            {
                var client = _httpClientFactory.CreateClient("ReprocessApiClient");
                var response = await client.PostAsJsonAsync("/api/Management/ReprocessCases", new
                {
                    radNumber,
                    isCrossSelling
                });

                if (response.IsSuccessStatusCode)
                {
                    return (true, null);
                }

                var body = await response.Content.ReadAsStringAsync();
                _logger.LogWarning("Fallo en ReprocessCases. Estado: {StatusCode}, Error: {Error}", response.StatusCode, body);
                return (false, $"Estado HTTP {response.StatusCode}: {body}");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error al consumir ReprocessCases.");
                return (false, ex.Message);
            }
        }

        public async Task<(bool Success, string? ErrorMessage)> SaveSignatureAsync(string adicionalJson)
        {
            try
            {
                var client = _httpClientFactory.CreateClient("SignatureApiClient");
                var content = new StringContent(adicionalJson, System.Text.Encoding.UTF8, "application/json");
                var response = await client.PostAsync("/api/Signature/Save", content);

                if (response.IsSuccessStatusCode)
                {
                    return (true, null);
                }

                var body = await response.Content.ReadAsStringAsync();
                _logger.LogWarning("Fallo en Signature/Save. Estado: {StatusCode}, Error: {Error}", response.StatusCode, body);
                return (false, $"Estado HTTP {response.StatusCode}: {body}");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error al consumir Signature/Save.");
                return (false, ex.Message);
            }
        }

        public async Task<(bool Success, string? ErrorMessage)> UpdateStateAsync(long signProcessId, string signCodeState, string bioCodeState)
        {
            try
            {
                var client = _httpClientFactory.CreateClient("SignatureApiClient");
                var response = await client.PatchAsJsonAsync("/api/Signature/UpdateState", new
                {
                    signProcessId,
                    signCodeState,
                    bioCodeState
                });

                if (response.IsSuccessStatusCode)
                {
                    return (true, null);
                }

                var body = await response.Content.ReadAsStringAsync();
                _logger.LogWarning("Fallo en Signature/UpdateState. Estado: {StatusCode}, Error: {Error}", response.StatusCode, body);
                return (false, $"Estado HTTP {response.StatusCode}: {body}");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error al consumir Signature/UpdateState.");
                return (false, ex.Message);
            }
        }
    }
}
