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
        /// Elimina las entradas verificadas cuyo tiempo de retención ya expiró.
        /// Devuelve la cantidad de entradas eliminadas.
        /// </summary>
        int EliminarVencidos();
    }
}
