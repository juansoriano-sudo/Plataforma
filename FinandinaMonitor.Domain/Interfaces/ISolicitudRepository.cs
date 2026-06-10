using System.Collections.Generic;
using System.Threading.Tasks;
using FinandinaMonitor.Domain.Entities;

namespace FinandinaMonitor.Domain.Interfaces
{
    public interface ISolicitudRepository
    {
        Task<IEnumerable<SolicitudFirma>> GetPendientesProcesarAsync(int estadoFirma = 100, int estadoBiometria = 70);
    }
}
