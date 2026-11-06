using System;
using System.Threading;
using System.Threading.Tasks;
using FinandinaMonitor.Domain.Helpers;
using FinandinaMonitor.Domain.Interfaces;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace FinandinaMonitor.Infrastructure.Services
{
    /// <summary>
    /// Verifica, cada 5 segundos, las firmas reprocesadas para confirmar si avanzaron
    /// (Firma 1000 / Biometría 70). Reintenta cada 5 segundos hasta que la firma avance;
    /// solo se marca como "No avanzó" de forma definitiva si, tras <see cref="VentanaMaximaEspera"/>
    /// desde el reproceso, sigue sin llegar a Firma 1000 / Biometría 70.
    /// </summary>
    public class HistoricoVerificacionBackgroundService : BackgroundService
    {
        private static readonly TimeSpan IntervaloVerificacion = TimeSpan.FromSeconds(5);
        private static readonly TimeSpan VentanaMaximaEspera = TimeSpan.FromMinutes(5);
        private const int EstadoFirmaExitoso = 1000;
        private const int EstadoBiometriaExitoso = 70;

        private readonly IServiceScopeFactory _scopeFactory;
        private readonly IHistoricoReprocesoStore _historicoStore;
        private readonly ILogger<HistoricoVerificacionBackgroundService> _logger;

        public HistoricoVerificacionBackgroundService(
            IServiceScopeFactory scopeFactory,
            IHistoricoReprocesoStore historicoStore,
            ILogger<HistoricoVerificacionBackgroundService> logger)
        {
            _scopeFactory = scopeFactory;
            _historicoStore = historicoStore;
            _logger = logger;
        }

        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            while (!stoppingToken.IsCancellationRequested)
            {
                try
                {
                    await VerificarPendientesAsync(stoppingToken);
                    _historicoStore.EliminarVencidos();
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error al verificar el histórico de firmas reprocesadas.");
                }

                try
                {
                    await Task.Delay(IntervaloVerificacion, stoppingToken);
                }
                catch (TaskCanceledException)
                {
                    // La aplicación se está deteniendo.
                }
            }
        }

        private async Task VerificarPendientesAsync(CancellationToken stoppingToken)
        {
            var pendientes = _historicoStore.ObtenerPendientesParaVerificar(TimeSpan.Zero);
            if (pendientes.Count == 0)
            {
                return;
            }

            using var scope = _scopeFactory.CreateScope();
            var repository = scope.ServiceProvider.GetRequiredService<ISolicitudRepository>();

            foreach (var item in pendientes)
            {
                if (stoppingToken.IsCancellationRequested)
                {
                    break;
                }

                var estadoActual = await repository.GetEstadoActualAsync(item.IdSolicitud);
                if (estadoActual is null)
                {
                    continue;
                }

                var avanzo = estadoActual.Value.IdEstadoFirma == EstadoFirmaExitoso
                             && estadoActual.Value.IdEstadoBiometria == EstadoBiometriaExitoso;

                if (avanzo)
                {
                    // Éxito confirmado: se marca como verificado de forma definitiva.
                    _historicoStore.MarcarVerificado(
                        item.Id,
                        estadoActual.Value.IdEstadoFirma,
                        estadoActual.Value.IdEstadoBiometria,
                        avanzo: true);
                }
                else if (HoraLocal.Ahora - item.FechaReproceso >= VentanaMaximaEspera)
                {
                    // Se agotó la ventana de espera sin llegar a Firma 1000 / Biometría 70: no avanzó.
                    _historicoStore.MarcarVerificado(
                        item.Id,
                        estadoActual.Value.IdEstadoFirma,
                        estadoActual.Value.IdEstadoBiometria,
                        avanzo: false);
                }
                // En caso contrario, se deja pendiente para reintentar en el próximo ciclo.
            }
        }
    }
}
