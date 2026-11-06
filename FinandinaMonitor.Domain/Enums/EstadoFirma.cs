using System.Collections.Generic;

namespace FinandinaMonitor.Domain.Enums
{
    public enum EstadoFirma
    {
        Encolada = 100,
        Exitosa = 1000,
        Actualizada = 20
    }

    public static class EstadoFirmaCatalogo
    {
        public static readonly IReadOnlyDictionary<int, string> Nombres = new Dictionary<int, string>
        {
            { (int)EstadoFirma.Encolada, "Encolada (100)" },
            { (int)EstadoFirma.Exitosa, "Exitosa (1000)" },
            { (int)EstadoFirma.Actualizada, "Actualizada (20)" }
        };

        public static string ObtenerNombre(int idEstadoFirma) =>
            Nombres.TryGetValue(idEstadoFirma, out var nombre) ? nombre : $"Estado {idEstadoFirma}";
    }
}
