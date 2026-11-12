using System.Threading.Tasks;

namespace FinandinaMonitor.Domain.Interfaces
{
    public interface IActividadLogger
    {
        /// <summary>
        /// Registra una línea de actividad en el archivo del día actual (uno por día, en la carpeta configurada).
        /// </summary>
        Task RegistrarAsync(string? usuario, string accion, string detalle);
    }
}
