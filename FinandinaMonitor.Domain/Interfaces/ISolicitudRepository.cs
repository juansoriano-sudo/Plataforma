using System.Collections.Generic;
using System.Threading.Tasks;
using FinandinaMonitor.Domain.Entities;

namespace FinandinaMonitor.Domain.Interfaces
{
    public interface ISolicitudRepository
    {
        Task<IEnumerable<SolicitudFirma>> GetPendientesProcesarAsync(int estadoFirma = 100, int estadoBiometria = 70);
        Task<IEnumerable<SolicitudFirma>> GetPendientesPorEstadoBiometriaAsync(int estadoBiometria = 2000);
        Task<IEnumerable<SolicitudFirma>> BuscarSolicitudesAsync(string? termino, int? estadoFirma = null, int? estadoBiometria = null);
        Task<int> GetCountExitosasHoyAsync(System.DateTime fechaInicio, System.DateTime fechaFin, int estadoFirma = 1000, int estadoBiometria = 70);
        Task<(int IdEstadoFirma, int IdEstadoBiometria)?> GetEstadoActualAsync(long idSolicitud);

        /// <summary>
        /// Cuenta las solicitudes que cumplen el filtro dado (usado por las alertas de monitoreo temporales).
        /// </summary>
        Task<int> ContarPorFiltroAsync(string? termino, int? estadoFirma, int? estadoBiometria);
    }
}
