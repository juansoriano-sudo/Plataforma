using System;
using System.Threading;
using System.Threading.Tasks;
using FinandinaMonitor.Domain.Interfaces;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace FinandinaMonitor.Infrastructure.Services
{
    /// <summary>
    /// Evalúa, cada 30 segundos, las alertas de monitoreo temporales creadas desde el Buscador:
    /// cuenta cuántas solicitudes cumplen el filtro de cada alerta activa y la marca como "Disparada"
    /// si el conteo alcanza el umbral configurado. Las alertas se desactivan automáticamente al vencer
    /// su ventana de tiempo.
    /// </summary>
    public class AlertaMonitoreoBackgroundService : BackgroundService
    {
        private static readonly TimeSpan IntervaloEvaluacion = TimeSpan.FromSeconds(30);

        private readonly IServiceScopeFactory _scopeFactory;
        private readonly IAlertaMonitoreoStore _alertaStore;
        private readonly ILogger<AlertaMonitoreoBackgroundService> _logger;

        public AlertaMonitoreoBackgroundService(
            IServiceScopeFactory scopeFactory,
            IAlertaMonitoreoStore alertaStore,
            ILogger<AlertaMonitoreoBackgroundService> logger)
        {
            _scopeFactory = scopeFactory;
            _alertaStore = alertaStore;
            _logger = logger;
        }

        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            while (!stoppingToken.IsCancellationRequested)
            {
                try
                {
                    await EvaluarAlertasActivasAsync(stoppingToken);
                    _alertaStore.DesactivarVencidas();
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error al evaluar las alertas de monitoreo temporales.");
                }

                try
                {
                    await Task.Delay(IntervaloEvaluacion, stoppingToken);
                }
                catch (TaskCanceledException)
                {
                    // La aplicación se está deteniendo.
                }
            }
        }

        private async Task EvaluarAlertasActivasAsync(CancellationToken stoppingToken)
        {
            var activas = _alertaStore.ObtenerActivas();
            if (activas.Count == 0)
            {
                return;
            }

            using var scope = _scopeFactory.CreateScope();
            var repository = scope.ServiceProvider.GetRequiredService<ISolicitudRepository>();

            foreach (var alerta in activas)
            {
                if (stoppingToken.IsCancellationRequested)
                {
                    break;
                }

                var conteo = await repository.ContarPorFiltroAsync(alerta.Termino, alerta.EstadoFirma, alerta.EstadoBiometria);
                _alertaStore.ActualizarEvaluacion(alerta.Id, conteo, disparada: conteo >= alerta.Umbral);
            }
        }
    }
}
