using System.Collections.Generic;

namespace FinandinaMonitor.Domain.Enums
{
    public enum OrigenSolicitud
    {
        Agil = 1,
        Celerys = 2,
        Tcgarantizada = 3
    }

    public static class OrigenSolicitudCatalogo
    {
        public static readonly IReadOnlyDictionary<int, string> Nombres = new Dictionary<int, string>
        {
            { (int)OrigenSolicitud.Agil, "Agil" },
            { (int)OrigenSolicitud.Celerys, "Celerys" },
            { (int)OrigenSolicitud.Tcgarantizada, "Tcgarantizada" }
        };

        public static string ObtenerNombre(int idOrigen) =>
            Nombres.TryGetValue(idOrigen, out var nombre) ? nombre : $"Desconocido ({idOrigen})";
    }
}
