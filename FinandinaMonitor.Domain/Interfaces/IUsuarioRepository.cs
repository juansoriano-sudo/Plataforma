using System.Collections.Generic;
using System.Threading.Tasks;
using FinandinaMonitor.Domain.Entities;

namespace FinandinaMonitor.Domain.Interfaces
{
    public interface IUsuarioRepository
    {
        /// <summary>
        /// Crea la base/tabla de usuarios si no existe y siembra el admin inicial (ADMIN_USER/ADMIN_PASSWORD)
        /// si todavía no hay ningún usuario registrado.
        /// </summary>
        Task InicializarAsync();

        Task<Usuario?> ValidarCredencialesAsync(string username, string password);
        Task<IEnumerable<Usuario>> ObtenerTodosAsync();
        Task<bool> ExisteUsernameAsync(string username);

        Task<Usuario> CrearAsync(string username, string password, bool esAdmin, bool puedeBorrar, bool puedeReprocesar, bool puedeVerCompleto);

        Task ActualizarPermisosAsync(int id, bool esAdmin, bool puedeBorrar, bool puedeReprocesar, bool puedeVerCompleto, bool activo);

        Task CambiarPasswordAsync(int id, string nuevaPassword);
    }
}
