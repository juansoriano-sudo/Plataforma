using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using FinandinaMonitor.Domain.Entities;
using FinandinaMonitor.Domain.Helpers;
using FinandinaMonitor.Domain.Interfaces;

namespace FinandinaMonitor.Application.Services
{
    /// <summary>
    /// Almacén en memoria (singleton) del histórico de reprocesos.
    /// Se limita a las últimas <see cref="MaxItems"/> entradas para no crecer indefinidamente,
    /// y cada entrada se elimina <see cref="TiempoRetencion"/> después de ser verificada.
    /// </summary>
    public class HistoricoReprocesoStore : IHistoricoReprocesoStore
    {
        private const int MaxItems = 500;
        private static readonly TimeSpan TiempoRetencion = TimeSpan.FromMinutes(5);

        private readonly ConcurrentDictionary<Guid, HistoricoReproceso> _items = new();

        public void Registrar(HistoricoReproceso item)
        {
            _items[item.Id] = item;

            if (_items.Count > MaxItems)
            {
                var masAntiguos = _items.Values
                    .OrderBy(i => i.FechaReproceso)
                    .Take(_items.Count - MaxItems)
                    .Select(i => i.Id)
                    .ToList();

                foreach (var id in masAntiguos)
                {
                    _items.TryRemove(id, out _);
                }
            }
        }

        public void MarcarVerificado(Guid id, int estadoFirmaVerificado, int estadoBiometriaVerificado, bool avanzo)
        {
            if (_items.TryGetValue(id, out var item))
            {
                item.Verificado = true;
                item.EstadoFirmaVerificado = estadoFirmaVerificado;
                item.EstadoBiometriaVerificado = estadoBiometriaVerificado;
                item.Avanzo = avanzo;
                item.FechaVerificacion = HoraLocal.Ahora;
            }
        }

        public IReadOnlyList<HistoricoReproceso> ObtenerHistorico()
        {
            var ahora = HoraLocal.Ahora;
            return _items.Values
                .Where(i => !EstaVencido(i, ahora))
                .OrderByDescending(i => i.FechaReproceso)
                .ToList();
        }

        public int EliminarVencidos()
        {
            var ahora = HoraLocal.Ahora;
            var eliminados = 0;

            foreach (var item in _items.Values.Where(i => EstaVencido(i, ahora)).ToList())
            {
                if (_items.TryRemove(item.Id, out _))
                {
                    eliminados++;
                }
            }

            return eliminados;
        }

        /// <summary>
        /// Una entrada vence <see cref="TiempoRetencion"/> después de conocerse su resultado final
        /// (avanzó / no avanzó). Las que siguen pendientes de verificación no vencen.
        /// </summary>
        private static bool EstaVencido(HistoricoReproceso item, DateTime ahora)
        {
            return item.Verificado
                   && item.FechaVerificacion.HasValue
                   && (ahora - item.FechaVerificacion.Value) >= TiempoRetencion;
        }

        public IReadOnlyList<HistoricoReproceso> ObtenerPendientesParaVerificar(TimeSpan antiguedadMinima)
        {
            var ahora = HoraLocal.Ahora;
            return _items.Values
                .Where(i => !i.Verificado && (ahora - i.FechaReproceso) >= antiguedadMinima)
                .ToList();
        }
    }
}
