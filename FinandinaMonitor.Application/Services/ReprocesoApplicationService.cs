using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using FinandinaMonitor.Domain.Entities;
using FinandinaMonitor.Domain.Interfaces;

namespace FinandinaMonitor.Application.Services
{
    public class ReprocesoApplicationService
    {
        private readonly ISolicitudRepository _repository;

        public ReprocesoApplicationService(ISolicitudRepository repository)
        {
            _repository = repository;
        }

        public async Task<IEnumerable<SolicitudFirma>> ObtenerPendientesAsync(int estadoFirma = 100, int estadoBiometria = 70)
        {
            return await _repository.GetPendientesProcesarAsync(estadoFirma, estadoBiometria);
        }

        public async Task<IEnumerable<SolicitudFirma>> ObtenerPorEstadoBiometriaAsync(int estadoBiometria = 2000)
        {
            return await _repository.GetPendientesPorEstadoBiometriaAsync(estadoBiometria);
        }

        public async Task<IEnumerable<SolicitudFirma>> BuscarAsync(string? termino, int? estadoFirma = null, int? estadoBiometria = null)
        {
            return await _repository.BuscarSolicitudesAsync(termino, estadoFirma, estadoBiometria);
        }

        public async Task<int> ContarPorFiltroAsync(string? termino, int? estadoFirma, int? estadoBiometria)
        {
            return await _repository.ContarPorFiltroAsync(termino, estadoFirma, estadoBiometria);
        }

        public async Task<int> ObtenerCountExitosasHoyAsync()
        {
            var hoy = DateTime.Today;
            var manana = hoy.AddDays(1);
            return await _repository.GetCountExitosasHoyAsync(hoy, manana);
        }

        public async Task<(int IdEstadoFirma, int IdEstadoBiometria)?> ObtenerEstadoActualAsync(long idSolicitud)
        {
            return await _repository.GetEstadoActualAsync(idSolicitud);
        }
    }
}
