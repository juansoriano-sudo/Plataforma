using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using FinandinaMonitor.Domain.DTOs;
using FinandinaMonitor.Domain.Entities;
using FinandinaMonitor.Domain.Interfaces;

namespace FinandinaMonitor.Application.Services
{
    public class ReprocesoApplicationService
    {
        private readonly ISolicitudRepository _repository;
        private readonly IFirmaApiService _apiService;

        public ReprocesoApplicationService(ISolicitudRepository repository, IFirmaApiService apiService)
        {
            _repository = repository;
            _apiService = apiService;
        }

        /// <summary>
        /// Obtiene las solicitudes de firma encoladas y pendientes de procesamiento.
        /// </summary>
        public async Task<IEnumerable<SolicitudFirma>> ObtenerPendientesAsync(int estadoFirma = 100, int estadoBiometria = 70)
        {
            return await _repository.GetPendientesProcesarAsync(estadoFirma, estadoBiometria);
        }

        /// <summary>
        /// Reprocesa un conjunto de solicitudes seleccionadas, retornando un diccionario con el resultado de cada una (IdSolicitud -> Éxito/Error).
        /// </summary>
        public async Task<Dictionary<long, bool>> ReprocesarSeleccionadosAsync(IEnumerable<SolicitudFirma> solicitudes)
        {
            var dtos = solicitudes.Select(s => new ReprocesoRequestDto
            {
                IdSolicitud = s.IdSolicitud,
                RadNumber = s.RadNumber,
                NumeroDocumento = s.NumeroDocumento
            });

            // Use dynamic invocation to avoid compile-time dependency on a specific method name
            dynamic svc = _apiService;
            var result = await svc.ReprocesarEnBloqueAsync(dtos);
            return (Dictionary<long, bool>)result;
        }
    }
}
