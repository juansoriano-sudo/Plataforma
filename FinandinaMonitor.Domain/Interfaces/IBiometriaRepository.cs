using System.Threading.Tasks;
using FinandinaMonitor.Domain.Entities;

namespace FinandinaMonitor.Domain.Interfaces
{
    public interface IBiometriaRepository
    {
        /// <summary>
        /// Resume los intentos biométricos (histórico en ORQBIOMETRIA) del cliente dueño de la solicitud,
        /// a partir del IdCasoBiometria asociado en MotorFirma.Firma.Detalle.
        /// </summary>
        Task<IntentoBiometricoResumen?> ObtenerResumenPorSolicitudAsync(long idSolicitud);
    }
}
