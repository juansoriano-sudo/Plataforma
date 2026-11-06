using System.Collections.Generic;

namespace FinandinaMonitor.Domain.Enums
{
    public enum EstadoBiometria
    {
        Pendiente = 70,
        FueraDeLinea = 2000,
        Actualizada = 50
    }

    public static class EstadoBiometriaCatalogo
    {
        public static readonly IReadOnlyDictionary<int, string> Nombres = new Dictionary<int, string>
        {
            { (int)EstadoBiometria.Pendiente, "Pendiente (70)" },
            { (int)EstadoBiometria.FueraDeLinea, "Fuera de línea (2000)" },
            { (int)EstadoBiometria.Actualizada, "Actualizada (50)" }
        };

        public static string ObtenerNombre(int idEstadoBiometria) =>
            Nombres.TryGetValue(idEstadoBiometria, out var nombre) ? nombre : $"Estado {idEstadoBiometria}";
    }
}
