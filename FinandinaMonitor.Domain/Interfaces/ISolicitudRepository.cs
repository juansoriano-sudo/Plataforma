using System.Collections.Generic;
using System.Threading.Tasks;
using FinandinaMonitor.Domain.Entities;

namespace FinandinaMonitor.Domain.Interfaces
{
    public interface ISolicitudRepository
    {
        Task<IEnumerable<SolicitudFirma>> GetPendientesProcesarAsync(int estadoFirma = 100, int estadoBiometria = 70);
        Task<int> GetCountExitosasHoyAsync(System.DateTime fechaInicio, System.DateTime fechaFin, int estadoFirma = 1000, int estadoBiometria = 70);
    }
}
