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
    /// Almacén en memoria (singleton) de las alertas de monitoreo temporales creadas por el usuario
    /// desde el Buscador. Cada alerta vigila un filtro (Estado Firma / Estado Biometría / término)
    /// durante una ventana de tiempo limitada (<see cref="AlertaMonitoreo.DuracionMinutos"/>).
    /// </summary>
    public class AlertaMonitoreoStore : IAlertaMonitoreoStore
    {
        private const int MaxItems = 200;

        private readonly ConcurrentDictionary<Guid, AlertaMonitoreo> _items = new();

        public AlertaMonitoreo Crear(AlertaMonitoreo alerta)
        {
            alerta.FechaExpiracion = alerta.FechaCreacion.AddMinutes(alerta.DuracionMinutos);
            _items[alerta.Id] = alerta;

            if (_items.Count > MaxItems)
            {
                var masAntiguas = _items.Values
                    .OrderBy(i => i.FechaCreacion)
                    .Take(_items.Count - MaxItems)
                    .Select(i => i.Id)
                    .ToList();

                foreach (var id in masAntiguas)
                {
                    _items.TryRemove(id, out _);
                }
            }

            return alerta;
        }

        public IReadOnlyList<AlertaMonitoreo> ObtenerActivas()
        {
            return _items.Values
                .Where(a => a.Activa)
                .OrderByDescending(a => a.FechaCreacion)
                .ToList();
        }

        public IReadOnlyList<AlertaMonitoreo> ObtenerTodas()
        {
            return _items.Values
                .OrderByDescending(a => a.FechaCreacion)
                .ToList();
        }

        public void ActualizarEvaluacion(Guid id, int conteo, bool disparada)
        {
            if (_items.TryGetValue(id, out var alerta))
            {
                alerta.UltimoConteo = conteo;
                alerta.UltimaEvaluacion = HoraLocal.Ahora;

                if (disparada && !alerta.Disparada)
                {
                    alerta.Disparada = true;
                    alerta.FechaDisparo = HoraLocal.Ahora;
                }
            }
        }

        public void Desactivar(Guid id)
        {
            if (_items.TryGetValue(id, out var alerta))
            {
                alerta.Activa = false;
            }
        }

        public AlertaMonitoreo? Editar(Guid id, string descripcion, int? estadoFirma, int? estadoBiometria, string? termino, int umbral, int duracionMinutos)
        {
            if (!_items.TryGetValue(id, out var alerta) || !alerta.Activa)
            {
                return null;
            }

            alerta.Descripcion = descripcion;
            alerta.EstadoFirma = estadoFirma;
            alerta.EstadoBiometria = estadoBiometria;
            alerta.Termino = termino;
            alerta.Umbral = umbral;
            alerta.DuracionMinutos = duracionMinutos;
            alerta.FechaExpiracion = alerta.FechaCreacion.AddMinutes(duracionMinutos);

            // Al cambiar los criterios, se vuelve a vigilar desde cero.
            alerta.Disparada = false;
            alerta.FechaDisparo = null;
            alerta.UltimoConteo = 0;
            alerta.UltimaEvaluacion = null;

            return alerta;
        }

        public int DesactivarVencidas()
        {
            var ahora = HoraLocal.Ahora;
            var vencidas = 0;

            foreach (var alerta in _items.Values.Where(a => a.Activa && ahora >= a.FechaExpiracion).ToList())
            {
                alerta.Activa = false;
                vencidas++;
            }

            return vencidas;
        }
    }
}
