using System;
using System.Collections.Generic;
using FinandinaMonitor.Domain.Entities;

namespace FinandinaMonitor.Domain.Interfaces
{
    public interface IHistoricoReprocesoStore
    {
        void Registrar(HistoricoReproceso item);

        void MarcarVerificado(Guid id, int estadoFirmaVerificado, int estadoBiometriaVerificado, bool avanzo);

        IReadOnlyList<HistoricoReproceso> ObtenerHistorico();

        IReadOnlyList<HistoricoReproceso> ObtenerPendientesParaVerificar(TimeSpan antiguedadMinima);

        /// <summary>
        /// Indica si ya se registró un reproceso para esta solicitud dentro de la ventana dada
        /// (protección contra reprocesos duplicados, por ejemplo doble clic o varios usuarios a la vez).
        /// Si devuelve true, <paramref name="usuarioAnterior"/> trae quién lo disparó.
        /// </summary>
        bool FueReprocesadoRecientemente(long idSolicitud, TimeSpan ventana, out string? usuarioAnterior);

        /// <summary>
        /// Elimina las entradas verificadas cuyo tiempo de retención ya expiró.
        /// Devuelve la cantidad de entradas eliminadas.
        /// </summary>
        int EliminarVencidos();
    }
}
