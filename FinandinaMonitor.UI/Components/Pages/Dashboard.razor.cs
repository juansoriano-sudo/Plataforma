using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json.Nodes;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Components;
using Microsoft.AspNetCore.Components.Web;
using Microsoft.JSInterop;
using FinandinaMonitor.Domain.Entities;
using FinandinaMonitor.Domain.Enums;
using FinandinaMonitor.Domain.Helpers;
using FinandinaMonitor.Domain.Interfaces;
using FinandinaMonitor.Application.Services;

namespace FinandinaMonitor.UI.Components.Pages
{
    public class SolicitudItemViewModel
    {
        public SolicitudFirma Solicitud { get; set; } = default!;
        public bool IsSelected { get; set; }
        public string EstadoReproceso { get; set; } = string.Empty;
    }

    public class OrigenResumenViewModel
    {
        public int IdOrigen { get; set; }
        public string Nombre { get; set; } = string.Empty;
        public int Total { get; set; }
    }

    public partial class Dashboard : ComponentBase, IDisposable
    {
        protected const int MaxReprocesoSimultaneo = 5;

        protected IReadOnlyDictionary<int, string> OrigenesDisponibles => OrigenSolicitudCatalogo.Nombres;
        [Inject]
        public ReprocesoApplicationService ReprocesoService { get; set; } = default!;

        [Inject]
        public ILogApiService LogApiService { get; set; } = default!;

        [Inject]
        public IFirmaApiService FirmaApiService { get; set; } = default!;

        [Inject]
        public IReprocesoAvanzadoApiService ReprocesoAvanzadoApiService { get; set; } = default!;

        [Inject]
        public IHistoricoReprocesoStore HistoricoReprocesoStore { get; set; } = default!;

        [Inject]
        public IAlertaMonitoreoStore AlertaMonitoreoStore { get; set; } = default!;

        [Inject]
        public IJSRuntime JSRuntime { get; set; } = default!;

        private Timer? _refreshTimer;
        private Timer? _alertaRefreshTimer;

        protected List<SolicitudItemViewModel> Solicitudes100_70 { get; set; } = new();
        protected List<SolicitudItemViewModel> Solicitudes1000_70 { get; set; } = new();
        protected List<SolicitudItemViewModel> Solicitudes2000 { get; set; } = new();
        protected List<SolicitudItemViewModel> ResultadosBusqueda { get; set; } = new();

        protected int ActiveTab { get; set; } = 1;

        protected List<SolicitudItemViewModel> CurrentSolicitudes => ActiveAlertaId.HasValue
            ? DesgloceAlertaActual
            : ActiveTab switch
            {
                1 => Solicitudes100_70,
                2 => Solicitudes1000_70,
                3 => Solicitudes2000,
                4 => ResultadosBusqueda,
                _ => ResultadosBusqueda
            };

        protected IReadOnlyList<HistoricoReproceso> Historico => HistoricoReprocesoStore.ObtenerHistorico();

        protected IEnumerable<SolicitudItemViewModel> FilteredSolicitudes
        {
            get
            {
                var query = CurrentSolicitudes.AsEnumerable();

                if (!string.IsNullOrWhiteSpace(SearchTerm))
                {
                    query = query.Where(s =>
                        s.Solicitud.IdSolicitud.ToString().Contains(SearchTerm, StringComparison.OrdinalIgnoreCase) ||
                        (s.Solicitud.RadNumber != null && s.Solicitud.RadNumber.Contains(SearchTerm, StringComparison.OrdinalIgnoreCase)) ||
                        (s.Solicitud.NumeroDocumento != null && s.Solicitud.NumeroDocumento.Contains(SearchTerm, StringComparison.OrdinalIgnoreCase)));
                }

                if (ActiveTab == 1 && (FechaDesde.HasValue || FechaHasta.HasValue))
                {
                    query = query.Where(s =>
                        (!FechaDesde.HasValue || s.Solicitud.FechaCreacion.Date >= FechaDesde.Value.Date) &&
                        (!FechaHasta.HasValue || s.Solicitud.FechaCreacion.Date <= FechaHasta.Value.Date));
                }

                if (SelectedOrigen.HasValue)
                {
                    query = query.Where(s => s.Solicitud.Origen == SelectedOrigen.Value);
                }

                return query;
            }
        }

        protected string SearchTerm { get; set; } = "";

        protected DateTime? FechaDesde { get; set; }
        protected DateTime? FechaHasta { get; set; }
        protected int? SelectedOrigen { get; set; }

        protected string BusquedaTermino { get; set; } = "";
        protected int? BusquedaEstadoFirma { get; set; }
        protected int? BusquedaEstadoBiometria { get; set; }
        protected bool IsBuscando { get; set; } = false;
        protected string BusquedaMensaje { get; set; } = "";

        protected IReadOnlyDictionary<int, string> EstadosFirmaDisponibles => EstadoFirmaCatalogo.Nombres;
        protected IReadOnlyDictionary<int, string> EstadosBiometriaDisponibles => EstadoBiometriaCatalogo.Nombres;

        // --- Alertas de monitoreo temporales ---
        protected bool MostrarPanelAlerta { get; set; } = false;
        protected bool OfertaAlertaDescartada { get; set; } = false;
        protected int UmbralAlerta { get; set; } = 1;
        protected int DuracionAlertaValor { get; set; } = 30;
        protected string DuracionAlertaUnidad { get; set; } = "min";
        protected string? AlertaCreadaMensaje { get; set; }

        private static int ConvertirADuracionMinutos(int valor, string unidad) =>
            unidad == "hora" ? valor * 60 : valor;

        protected IReadOnlyList<AlertaMonitoreo> AlertasActivas => AlertaMonitoreoStore.ObtenerActivas();

        protected Guid? ActiveAlertaId { get; set; }
        protected AlertaMonitoreo? AlertaSeleccionada =>
            ActiveAlertaId.HasValue ? AlertasActivas.FirstOrDefault(a => a.Id == ActiveAlertaId.Value) : null;
        protected List<SolicitudItemViewModel> DesgloceAlertaActual { get; set; } = new();
        protected bool IsCargandoDesglose { get; set; } = false;

        protected bool PuedeOfrecerAlerta =>
            ActiveTab == 4 && !IsBuscando && !OfertaAlertaDescartada &&
            (BusquedaEstadoFirma.HasValue || BusquedaEstadoBiometria.HasValue);

        protected int TotalEnColaRango => FilteredSolicitudes.Count();

        protected List<OrigenResumenViewModel> TotalEnColaPorOrigen =>
            Solicitudes100_70
                .GroupBy(s => s.Solicitud.Origen)
                .Select(g => new OrigenResumenViewModel
                {
                    IdOrigen = g.Key,
                    Nombre = OrigenSolicitudCatalogo.ObtenerNombre(g.Key),
                    Total = g.Count()
                })
                .OrderBy(r => r.IdOrigen)
                .ToList();

        protected bool IsLoading { get; set; } = true;
        protected bool IsProcessing { get; set; } = false;
        protected int ProgressPercent { get; set; } = 0;
        protected string AlertMessage { get; set; } = "";
        protected bool IsAlertError { get; set; } = false;
        protected bool IsDarkMode { get; set; } = true;
        
        protected int ExitosasHoyCount { get; set; } = 0;

        protected int SelectedCount => CurrentSolicitudes.Count(s => s.IsSelected);
        protected bool IsAllSelected => FilteredSolicitudes.Any() && FilteredSolicitudes.All(s => s.IsSelected);

        protected override async Task OnInitializedAsync()
        {
            await CargarDatosAsync();
            _refreshTimer = new Timer(async _ =>
            {
                await InvokeAsync(async () =>
                {
                    if (!IsProcessing)
                    {
                        await CargarDatosAsync();
                    }
                });
            }, null, TimeSpan.FromMinutes(2), TimeSpan.FromMinutes(2));

            _alertaRefreshTimer = new Timer(async _ =>
            {
                await InvokeAsync(async () =>
                {
                    var alertaActiva = AlertaSeleccionada;
                    if (alertaActiva is not null && !IsCargandoDesglose)
                    {
                        await CargarDesgloceAlertaAsync(alertaActiva);
                    }
                    else
                    {
                        StateHasChanged();
                    }
                });
            }, null, TimeSpan.FromSeconds(15), TimeSpan.FromSeconds(15));
        }

        protected override async Task OnAfterRenderAsync(bool firstRender)
        {
            if (firstRender)
            {
                await JSRuntime.InvokeVoidAsync("document.documentElement.setAttribute", "data-theme", "dark");
            }
        }

        public void Dispose()
        {
            _refreshTimer?.Dispose();
            _alertaRefreshTimer?.Dispose();
        }

        protected async Task SetTab(int tabIndex)
        {
            ActiveTab = tabIndex;
            ActiveAlertaId = null;
            DesgloceAlertaActual.Clear();
            SearchTerm = "";
            FechaDesde = null;
            FechaHasta = null;
            SelectedOrigen = null;
            MostrarModalConfirmacionBorrado = false;
            BusquedaTermino = "";
            BusquedaEstadoFirma = null;
            BusquedaEstadoBiometria = null;
            BusquedaMensaje = "";
            MostrarPanelAlerta = false;
            OfertaAlertaDescartada = false;
            AlertaCreadaMensaje = null;
            ResultadosBusqueda.Clear();
            await InvokeAsync(StateHasChanged);
        }

        protected async Task EjecutarBusquedaAsync()
        {
            var hayTermino = !string.IsNullOrWhiteSpace(BusquedaTermino);
            var hayFiltroEstado = BusquedaEstadoFirma.HasValue || BusquedaEstadoBiometria.HasValue;

            if ((!hayTermino && !hayFiltroEstado) || IsBuscando) return;

            IsBuscando = true;
            BusquedaMensaje = "";
            MostrarPanelAlerta = false;
            OfertaAlertaDescartada = false;
            AlertaCreadaMensaje = null;
            await InvokeAsync(StateHasChanged);

            try
            {
                var resultados = await ReprocesoService.BuscarAsync(
                    hayTermino ? BusquedaTermino : null,
                    BusquedaEstadoFirma,
                    BusquedaEstadoBiometria);

                ResultadosBusqueda = resultados.Select(s => new SolicitudItemViewModel
                {
                    Solicitud = s,
                    IsSelected = false,
                    EstadoReproceso = string.Empty
                }).ToList();

                BusquedaMensaje = ResultadosBusqueda.Any()
                    ? ""
                    : "No se encontraron solicitudes con esos criterios.";
            }
            catch (Exception ex)
            {
                BusquedaMensaje = $"Error al buscar: {ex.Message}";
                ResultadosBusqueda.Clear();
            }
            finally
            {
                IsBuscando = false;
                await InvokeAsync(StateHasChanged);
            }
        }

        protected async Task OnBusquedaEstadoFirmaInput(ChangeEventArgs e)
        {
            var value = e.Value?.ToString();
            BusquedaEstadoFirma = int.TryParse(value, out var codigo) ? codigo : null;
            await InvokeAsync(StateHasChanged);
        }

        protected async Task OnBusquedaEstadoBiometriaInput(ChangeEventArgs e)
        {
            var value = e.Value?.ToString();
            BusquedaEstadoBiometria = int.TryParse(value, out var codigo) ? codigo : null;
            await InvokeAsync(StateHasChanged);
        }

        protected void AbrirPanelAlerta()
        {
            MostrarPanelAlerta = true;
            AlertaCreadaMensaje = null;
        }

        protected void CancelarCreacionAlerta()
        {
            MostrarPanelAlerta = false;
        }

        protected async Task ConfirmarCreacionAlertaAsync()
        {
            if (UmbralAlerta < 1) UmbralAlerta = 1;
            if (DuracionAlertaValor < 1) DuracionAlertaValor = 1;

            var duracionMinutos = ConvertirADuracionMinutos(DuracionAlertaValor, DuracionAlertaUnidad);

            var descripcionPartes = new List<string>();
            if (BusquedaEstadoFirma.HasValue)
            {
                descripcionPartes.Add($"Firma = {EstadoFirmaCatalogo.ObtenerNombre(BusquedaEstadoFirma.Value)}");
            }
            if (BusquedaEstadoBiometria.HasValue)
            {
                descripcionPartes.Add($"Biometría = {EstadoBiometriaCatalogo.ObtenerNombre(BusquedaEstadoBiometria.Value)}");
            }

            var alerta = new AlertaMonitoreo
            {
                Descripcion = string.Join(" / ", descripcionPartes),
                EstadoFirma = BusquedaEstadoFirma,
                EstadoBiometria = BusquedaEstadoBiometria,
                Termino = string.IsNullOrWhiteSpace(BusquedaTermino) ? null : BusquedaTermino,
                Umbral = UmbralAlerta,
                DuracionMinutos = duracionMinutos
            };

            AlertaMonitoreoStore.Crear(alerta);

            MostrarPanelAlerta = false;
            var duracionTexto = DuracionAlertaUnidad == "hora"
                ? $"{DuracionAlertaValor} h"
                : $"{DuracionAlertaValor} min";
            AlertaCreadaMensaje = $"Alerta temporal creada: se vigilará \"{alerta.Descripcion}\" durante {duracionTexto} (umbral: {UmbralAlerta}).";

            ActiveAlertaId = alerta.Id;
            await CargarDesgloceAlertaAsync(alerta);
        }

        protected async Task SeleccionarTabAlertaAsync(Guid id)
        {
            ActiveAlertaId = id;
            var alerta = AlertasActivas.FirstOrDefault(a => a.Id == id);
            if (alerta is not null)
            {
                await CargarDesgloceAlertaAsync(alerta);
            }
        }

        protected async Task CargarDesgloceAlertaAsync(AlertaMonitoreo? alerta)
        {
            if (alerta is null || IsCargandoDesglose) return;

            IsCargandoDesglose = true;
            await InvokeAsync(StateHasChanged);

            try
            {
                var resultados = await ReprocesoService.BuscarAsync(alerta.Termino, alerta.EstadoFirma, alerta.EstadoBiometria);
                DesgloceAlertaActual = resultados.Select(s => new SolicitudItemViewModel
                {
                    Solicitud = s,
                    IsSelected = false,
                    EstadoReproceso = string.Empty
                }).ToList();
            }
            catch (Exception)
            {
                DesgloceAlertaActual.Clear();
            }
            finally
            {
                IsCargandoDesglose = false;
                await InvokeAsync(StateHasChanged);
            }
        }

        protected bool MostrarModalConfirmacionDetenerAlerta { get; set; } = false;
        protected Guid? AlertaPendienteDetenerId { get; set; }
        protected string? AlertaPendienteDetenerDescripcion { get; set; }

        protected void AbrirModalConfirmacionDetenerAlerta(Guid id, string? descripcion)
        {
            AlertaPendienteDetenerId = id;
            AlertaPendienteDetenerDescripcion = descripcion;
            MostrarModalConfirmacionDetenerAlerta = true;
        }

        protected void CerrarModalConfirmacionDetenerAlerta()
        {
            MostrarModalConfirmacionDetenerAlerta = false;
            AlertaPendienteDetenerId = null;
            AlertaPendienteDetenerDescripcion = null;
        }

        protected async Task ConfirmarDetenerAlertaAsync()
        {
            if (!AlertaPendienteDetenerId.HasValue)
            {
                CerrarModalConfirmacionDetenerAlerta();
                return;
            }

            var id = AlertaPendienteDetenerId.Value;
            AlertaMonitoreoStore.Desactivar(id);
            MostrarModalConfirmacionDetenerAlerta = false;
            AlertaPendienteDetenerId = null;
            AlertaPendienteDetenerDescripcion = null;

            if (ActiveAlertaId == id)
            {
                ActiveAlertaId = null;
                DesgloceAlertaActual.Clear();
                await SetTab(4);
            }
            else
            {
                await InvokeAsync(StateHasChanged);
            }
        }

        protected bool MostrarModalEditarAlerta { get; set; } = false;
        protected Guid? AlertaEditandoId { get; set; }
        protected int? EditAlertaEstadoFirma { get; set; }
        protected int? EditAlertaEstadoBiometria { get; set; }
        protected string EditAlertaTermino { get; set; } = "";
        protected int EditAlertaUmbral { get; set; } = 1;
        protected int EditAlertaDuracionValor { get; set; } = 30;
        protected string EditAlertaDuracionUnidad { get; set; } = "min";

        protected void AbrirModalEditarAlerta(AlertaMonitoreo alerta)
        {
            AlertaEditandoId = alerta.Id;
            EditAlertaEstadoFirma = alerta.EstadoFirma;
            EditAlertaEstadoBiometria = alerta.EstadoBiometria;
            EditAlertaTermino = alerta.Termino ?? "";
            EditAlertaUmbral = alerta.Umbral;

            if (alerta.DuracionMinutos > 0 && alerta.DuracionMinutos % 60 == 0)
            {
                EditAlertaDuracionValor = alerta.DuracionMinutos / 60;
                EditAlertaDuracionUnidad = "hora";
            }
            else
            {
                EditAlertaDuracionValor = alerta.DuracionMinutos;
                EditAlertaDuracionUnidad = "min";
            }

            MostrarModalEditarAlerta = true;
        }

        protected void CerrarModalEditarAlerta()
        {
            MostrarModalEditarAlerta = false;
            AlertaEditandoId = null;
        }

        protected async Task OnEditAlertaEstadoFirmaInput(ChangeEventArgs e)
        {
            var value = e.Value?.ToString();
            EditAlertaEstadoFirma = int.TryParse(value, out var codigo) ? codigo : null;
            await Task.CompletedTask;
        }

        protected async Task OnEditAlertaEstadoBiometriaInput(ChangeEventArgs e)
        {
            var value = e.Value?.ToString();
            EditAlertaEstadoBiometria = int.TryParse(value, out var codigo) ? codigo : null;
            await Task.CompletedTask;
        }

        protected async Task ConfirmarEditarAlertaAsync()
        {
            if (!AlertaEditandoId.HasValue) return;

            if (EditAlertaUmbral < 1) EditAlertaUmbral = 1;
            if (EditAlertaDuracionValor < 1) EditAlertaDuracionValor = 1;

            var duracionMinutos = ConvertirADuracionMinutos(EditAlertaDuracionValor, EditAlertaDuracionUnidad);

            var descripcionPartes = new List<string>();
            if (EditAlertaEstadoFirma.HasValue)
            {
                descripcionPartes.Add($"Firma = {EstadoFirmaCatalogo.ObtenerNombre(EditAlertaEstadoFirma.Value)}");
            }
            if (EditAlertaEstadoBiometria.HasValue)
            {
                descripcionPartes.Add($"Biometría = {EstadoBiometriaCatalogo.ObtenerNombre(EditAlertaEstadoBiometria.Value)}");
            }

            var termino = string.IsNullOrWhiteSpace(EditAlertaTermino) ? null : EditAlertaTermino.Trim();
            var descripcion = string.Join(" / ", descripcionPartes);

            var actualizada = AlertaMonitoreoStore.Editar(
                AlertaEditandoId.Value,
                descripcion,
                EditAlertaEstadoFirma,
                EditAlertaEstadoBiometria,
                termino,
                EditAlertaUmbral,
                duracionMinutos);

            MostrarModalEditarAlerta = false;
            AlertaEditandoId = null;

            if (actualizada is not null && ActiveAlertaId == actualizada.Id)
            {
                await CargarDesgloceAlertaAsync(actualizada);
            }
            else
            {
                await InvokeAsync(StateHasChanged);
            }
        }

        protected async Task OnBusquedaKeyUp(KeyboardEventArgs e)
        {
            if (e.Key == "Enter")
            {
                await EjecutarBusquedaAsync();
            }
        }

        protected void LimpiarFiltroFechas()
        {
            FechaDesde = null;
            FechaHasta = null;
        }

        protected async Task OnOrigenChanged(ChangeEventArgs e)
        {
            var value = e.Value?.ToString();
            SelectedOrigen = string.IsNullOrEmpty(value) ? null : int.Parse(value);
            await InvokeAsync(StateHasChanged);
        }

        protected HashSet<long> CopiandoAdicional { get; } = new();
        protected HashSet<long> AdicionalCopiado { get; } = new();

        protected async Task CopiarAdicionalAsync(SolicitudItemViewModel item)
        {
            var idSolicitud = item.Solicitud.IdSolicitud;
            if (!CopiandoAdicional.Add(idSolicitud)) return;
            await InvokeAsync(StateHasChanged);

            try
            {
                var logResult = await LogApiService.GetAdicionalAsync(idSolicitud);
                if (!logResult.Success || string.IsNullOrWhiteSpace(logResult.Adicional))
                {
                    AlertMessage = $"No se pudo obtener el Adicional para la solicitud {idSolicitud}: {logResult.ErrorMessage}";
                    IsAlertError = true;
                    return;
                }

                await JSRuntime.InvokeVoidAsync("navigator.clipboard.writeText", logResult.Adicional);

                AdicionalCopiado.Add(idSolicitud);
                _ = OcultarIndicadorCopiadoAsync(idSolicitud);
            }
            catch (Exception ex)
            {
                AlertMessage = $"Error al copiar el Adicional de la solicitud {idSolicitud}: {ex.Message}";
                IsAlertError = true;
            }
            finally
            {
                CopiandoAdicional.Remove(idSolicitud);
                await InvokeAsync(StateHasChanged);
            }
        }

        private async Task OcultarIndicadorCopiadoAsync(long idSolicitud)
        {
            await Task.Delay(TimeSpan.FromSeconds(1.8));
            AdicionalCopiado.Remove(idSolicitud);
            await InvokeAsync(StateHasChanged);
        }

        protected async Task ToggleTheme()
        {
            IsDarkMode = !IsDarkMode;
            var theme = IsDarkMode ? "dark" : "light";
            await JSRuntime.InvokeVoidAsync("document.documentElement.setAttribute", "data-theme", theme);
        }

        protected async Task CargarDatosAsync()
        {
            IsLoading = true;
            AlertMessage = "";
            await InvokeAsync(StateHasChanged);

            try
            {
                var result100 = await ReprocesoService.ObtenerPendientesAsync(estadoFirma: 100, estadoBiometria: 70);
                var result1000 = await ReprocesoService.ObtenerPendientesAsync(estadoFirma: 1000, estadoBiometria: 70);
                var result2000 = await ReprocesoService.ObtenerPorEstadoBiometriaAsync(estadoBiometria: 2000);

                Solicitudes100_70 = result100.Select(s => new SolicitudItemViewModel
                {
                    Solicitud = s,
                    IsSelected = false,
                    EstadoReproceso = string.Empty
                }).ToList();

                Solicitudes1000_70 = result1000.Select(s => new SolicitudItemViewModel
                {
                    Solicitud = s,
                    IsSelected = false,
                    EstadoReproceso = string.Empty
                }).ToList();

                Solicitudes2000 = result2000.Select(s => new SolicitudItemViewModel
                {
                    Solicitud = s,
                    IsSelected = false,
                    EstadoReproceso = string.Empty
                }).ToList();

                ExitosasHoyCount = await ReprocesoService.ObtenerCountExitosasHoyAsync();
            }
            catch (Exception ex)
            {
                AlertMessage = $"Error al cargar datos de SQL Server: {ex.Message}";
                IsAlertError = true;
                Solicitudes100_70.Clear();
                Solicitudes1000_70.Clear();
                Solicitudes2000.Clear();
            }
            finally
            {
                IsLoading = false;
                await InvokeAsync(StateHasChanged);
            }
        }

        protected void ToggleSelectAll(ChangeEventArgs e)
        {
            var isChecked = e.Value is bool b && b;

            if (!isChecked)
            {
                foreach (var item in FilteredSolicitudes)
                {
                    item.IsSelected = false;
                }
                return;
            }

            var seleccionActual = CurrentSolicitudes.Count(s => s.IsSelected);
            foreach (var item in FilteredSolicitudes)
            {
                if (item.IsSelected) continue;

                if (seleccionActual >= MaxReprocesoSimultaneo) break;

                item.IsSelected = true;
                seleccionActual++;
            }

            if (seleccionActual >= MaxReprocesoSimultaneo && FilteredSolicitudes.Any(s => !s.IsSelected))
            {
                AlertMessage = $"Solo se pueden reprocesar máximo {MaxReprocesoSimultaneo} firmas a la vez. Se seleccionaron las primeras {MaxReprocesoSimultaneo}.";
                IsAlertError = false;
            }
        }

        protected void ToggleSelectItem(SolicitudItemViewModel item, ChangeEventArgs e)
        {
            var isChecked = e.Value is bool b && b;

            if (isChecked && SelectedCount >= MaxReprocesoSimultaneo)
            {
                AlertMessage = $"Solo se pueden reprocesar máximo {MaxReprocesoSimultaneo} firmas a la vez. Deseleccione alguna para continuar.";
                IsAlertError = true;
                return;
            }

            item.IsSelected = isChecked;
        }

        protected async Task ReprocesarSeleccionadosAsync()
        {
            var selectedItems = CurrentSolicitudes.Where(s => s.IsSelected).Take(MaxReprocesoSimultaneo).ToList();
            if (!selectedItems.Any() || IsProcessing) return;

            IsProcessing = true;
            ProgressPercent = 0;
            AlertMessage = "Validando conexión a MariaDB...";
            IsAlertError = false;
            StateHasChanged();

            var health = await LogApiService.CheckHealthAsync();
            if (!health.IsConnected)
            {
                AlertMessage = $"Error de conexión con MariaDB/API: {health.Message}";
                IsAlertError = true;
                IsProcessing = false;
                StateHasChanged();
                return;
            }

            AlertMessage = "";
            StateHasChanged();

            int total = selectedItems.Count;
            int procesados = 0;
            int exitos = 0;
            int fallidos = 0;

            foreach (var item in selectedItems)
            {
                RegistrarEnHistorico(item.Solicitud, "Simple");

                try
                {
                    item.EstadoReproceso = "Consultando MariaDB...";
                    StateHasChanged();

                    var logResult = await LogApiService.GetAdicionalInicioFirmaAsync(item.Solicitud.IdSolicitud);

                    if (!logResult.Success)
                    {
                        item.EstadoReproceso = $"Error API: {logResult.ErrorMessage}";
                        item.IsSelected = false; // Auto uncheck on failure
                        fallidos++;
                    }
                    else
                    {
                        item.EstadoReproceso = "Enviando a Swagger...";
                        StateHasChanged();

                        var reprocesoResult = await FirmaApiService.ReprocesarSolicitudAsync(logResult.Adicional!);
                        if (reprocesoResult.Success)
                        {
                            item.EstadoReproceso = "Éxito";
                            item.IsSelected = false; // Auto uncheck on success
                            exitos++;
                            ExitosasHoyCount++; // Incrementamos el contador de exitosas hoy de forma optimista
                        }
                        else
                        {
                            item.EstadoReproceso = $"Fallo al reprocesar: {reprocesoResult.ErrorMessage}";
                            item.IsSelected = false;
                            fallidos++;
                        }
                    }
                }
                catch (Exception)
                {
                    item.EstadoReproceso = "Error crítico de ejecución";
                    item.IsSelected = false;
                    fallidos++;
                }

                procesados++;
                ProgressPercent = (int)((double)procesados / total * 100);
                StateHasChanged();
            }

            IsProcessing = false;

            if (fallidos == 0)
            {
                AlertMessage = $"Proceso finalizado. Se reprocesaron exitosamente {exitos} solicitudes.";
                IsAlertError = false;
            }
            else
            {
                AlertMessage = $"Proceso finalizado. {exitos} exitosos, {fallidos} fallidos. Verifique la columna de estado.";
                IsAlertError = true;
            }

            StateHasChanged();
        }

        protected bool IsProcessingAvanzado { get; set; } = false;
        protected bool MostrarModalConfirmacionBorrado { get; set; } = false;

        protected void AbrirModalConfirmacionBorrado()
        {
            if (SelectedCount == 0 || IsProcessing) return;
            MostrarModalConfirmacionBorrado = true;
        }

        protected void CerrarModalConfirmacionBorrado()
        {
            MostrarModalConfirmacionBorrado = false;
        }

        protected async Task ConfirmarBorradoDocumentosAsync()
        {
            MostrarModalConfirmacionBorrado = false;
            await ReprocesarAvanzadoSeleccionadosAsync();
        }

        protected async Task ReprocesarAvanzadoSeleccionadosAsync()
        {
            var selectedItems = CurrentSolicitudes.Where(s => s.IsSelected).Take(MaxReprocesoSimultaneo).ToList();
            if (!selectedItems.Any() || IsProcessing || IsProcessingAvanzado) return;

            IsProcessing = true;
            IsProcessingAvanzado = true;
            ProgressPercent = 0;
            AlertMessage = "";
            IsAlertError = false;
            StateHasChanged();

            int total = selectedItems.Count;
            int procesados = 0;
            int exitos = 0;
            int fallidos = 0;

            foreach (var item in selectedItems)
            {
                var idSolicitud = item.Solicitud.IdSolicitud;
                RegistrarEnHistorico(item.Solicitud, "Avanzado");

                try
                {
                    item.EstadoReproceso = "Consultando MariaDB...";
                    StateHasChanged();

                    var logResult = await LogApiService.GetAdicionalAsync(idSolicitud);
                    if (!logResult.Success || string.IsNullOrWhiteSpace(logResult.Adicional))
                    {
                        item.EstadoReproceso = $"Error MariaDB: {logResult.ErrorMessage}";
                        item.IsSelected = false;
                        fallidos++;
                        continue;
                    }

                    if (string.IsNullOrWhiteSpace(item.Solicitud.RadNumber))
                    {
                        item.EstadoReproceso = "Error: la solicitud no tiene RadNumber";
                        item.IsSelected = false;
                        fallidos++;
                        continue;
                    }

                    item.EstadoReproceso = "Reprocesando caso (ReprocessCases)...";
                    StateHasChanged();

                    var reprocessResult = await ReprocesoAvanzadoApiService.ReprocessCasesAsync(
                        item.Solicitud.RadNumber!, item.Solicitud.EsVentaCruzada);

                    if (!reprocessResult.Success)
                    {
                        item.EstadoReproceso = $"Fallo ReprocessCases: {reprocessResult.ErrorMessage}";
                        item.IsSelected = false;
                        fallidos++;
                        continue;
                    }

                    var adicionalPatched = PatchAdicionalJson(logResult.Adicional!, item.Solicitud.Origen);

                    item.EstadoReproceso = "Guardando firma (Signature/Save)...";
                    StateHasChanged();

                    var saveResult = await ReprocesoAvanzadoApiService.SaveSignatureAsync(adicionalPatched);
                    if (saveResult.Success)
                    {
                        item.EstadoReproceso = "Éxito";
                        item.IsSelected = false;
                        exitos++;
                        ExitosasHoyCount++;
                        continue;
                    }

                    item.EstadoReproceso = "Save falló, actualizando estado (UpdateState)...";
                    StateHasChanged();

                    var updateResult = await ReprocesoAvanzadoApiService.UpdateStateAsync(idSolicitud, "20", "50");
                    if (!updateResult.Success)
                    {
                        item.EstadoReproceso = $"Fallo Save y UpdateState: {saveResult.ErrorMessage} / {updateResult.ErrorMessage}";
                        item.IsSelected = false;
                        fallidos++;
                        continue;
                    }

                    item.EstadoReproceso = "Verificando estado en BD...";
                    StateHasChanged();

                    var estadoConfirmado = await EsperarEstadoAsync(idSolicitud, estadoFirmaEsperado: 20, estadoBiometriaEsperado: 50);
                    if (!estadoConfirmado)
                    {
                        item.EstadoReproceso = "Fallo: el estado (Firma 20 / Biometría 50) no se confirmó en la BD tras UpdateState";
                        item.IsSelected = false;
                        fallidos++;
                        continue;
                    }

                    item.EstadoReproceso = "Reintentando Signature/Save...";
                    StateHasChanged();

                    var retrySave = await ReprocesoAvanzadoApiService.SaveSignatureAsync(adicionalPatched);
                    if (retrySave.Success)
                    {
                        item.EstadoReproceso = "Éxito (tras UpdateState)";
                        item.IsSelected = false;
                        exitos++;
                        ExitosasHoyCount++;
                    }
                    else
                    {
                        item.EstadoReproceso = $"Fallo definitivo en Save: {retrySave.ErrorMessage}";
                        item.IsSelected = false;
                        fallidos++;
                    }
                }
                catch (Exception ex)
                {
                    item.EstadoReproceso = $"Error crítico: {ex.Message}";
                    item.IsSelected = false;
                    fallidos++;
                }
                finally
                {
                    procesados++;
                    ProgressPercent = (int)((double)procesados / total * 100);
                    StateHasChanged();
                }
            }

            IsProcessing = false;
            IsProcessingAvanzado = false;

            if (fallidos == 0)
            {
                AlertMessage = $"Proceso finalizado (nuevo flujo). Se reprocesaron exitosamente {exitos} solicitudes.";
                IsAlertError = false;
            }
            else
            {
                AlertMessage = $"Proceso finalizado (nuevo flujo). {exitos} exitosos, {fallidos} fallidos. Verifique la columna de estado.";
                IsAlertError = true;
            }

            StateHasChanged();
        }

        private static string PatchAdicionalJson(string adicionalJson, int origen)
        {
            var node = JsonNode.Parse(adicionalJson)?.AsObject()
                ?? throw new InvalidOperationException("El Adicional obtenido de MariaDB no es un JSON válido.");

            // Origin viaja como número en el JSON original; Reprocessing viaja como string ("false"/"true").
            node["Origin"] = origen;
            node["Reprocessing"] = "true";

            return node.ToJsonString();
        }

        private async Task<bool> EsperarEstadoAsync(long idSolicitud, int estadoFirmaEsperado, int estadoBiometriaEsperado)
        {
            const int intentosMax = 6;
            var espera = TimeSpan.FromSeconds(1.5);

            for (var intento = 0; intento < intentosMax; intento++)
            {
                var estado = await ReprocesoService.ObtenerEstadoActualAsync(idSolicitud);
                if (estado.HasValue &&
                    estado.Value.IdEstadoFirma == estadoFirmaEsperado &&
                    estado.Value.IdEstadoBiometria == estadoBiometriaEsperado)
                {
                    return true;
                }

                if (intento < intentosMax - 1)
                {
                    await Task.Delay(espera);
                }
            }

            return false;
        }

        protected void ClearAlert()
        {
            AlertMessage = "";
        }

        private void RegistrarEnHistorico(SolicitudFirma solicitud, string tipoReproceso)
        {
            HistoricoReprocesoStore.Registrar(new HistoricoReproceso
            {
                IdSolicitud = solicitud.IdSolicitud,
                RadNumber = solicitud.RadNumber,
                NumeroDocumento = solicitud.NumeroDocumento,
                TipoReproceso = tipoReproceso,
                EstadoFirmaInicial = solicitud.IdEstadoFirma,
                EstadoBiometriaInicial = solicitud.IdEstadoBiometria,
                FechaReproceso = HoraLocal.Ahora
            });
        }
    }
}
