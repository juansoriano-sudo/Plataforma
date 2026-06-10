using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Components;
using Microsoft.JSInterop;
using FinandinaMonitor.Domain.Entities;
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

    public partial class Dashboard : ComponentBase
    {
        [Inject]
        public ReprocesoApplicationService ReprocesoService { get; set; } = default!;

        [Inject]
        public ILogApiService LogApiService { get; set; } = default!;

        [Inject]
        public IFirmaApiService FirmaApiService { get; set; } = default!;

        [Inject]
        public IJSRuntime JSRuntime { get; set; } = default!;

        protected List<SolicitudItemViewModel> Solicitudes { get; set; } = new();

        protected IEnumerable<SolicitudItemViewModel> FilteredSolicitudes =>
            string.IsNullOrWhiteSpace(SearchTerm) 
                ? Solicitudes 
                : Solicitudes.Where(s => 
                    s.Solicitud.IdSolicitud.ToString().Contains(SearchTerm, StringComparison.OrdinalIgnoreCase) ||
                    (s.Solicitud.RadNumber != null && s.Solicitud.RadNumber.Contains(SearchTerm, StringComparison.OrdinalIgnoreCase)) ||
                    (s.Solicitud.NumeroDocumento != null && s.Solicitud.NumeroDocumento.Contains(SearchTerm, StringComparison.OrdinalIgnoreCase)));

        protected string SearchTerm { get; set; } = "";

        protected bool IsLoading { get; set; } = true;
        protected bool IsProcessing { get; set; } = false;
        protected int ProgressPercent { get; set; } = 0;
        protected string AlertMessage { get; set; } = "";
        protected bool IsAlertError { get; set; } = false;
        protected bool IsDarkMode { get; set; } = false;
        
        protected int ExitosasHoyCount { get; set; } = 0;

        protected int SelectedCount => Solicitudes.Count(s => s.IsSelected);
        protected bool IsAllSelected => FilteredSolicitudes.Any() && FilteredSolicitudes.All(s => s.IsSelected);

        protected override async Task OnInitializedAsync()
        {
            await CargarDatosAsync();
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
            StateHasChanged();

            try
            {
                var result = await ReprocesoService.ObtenerPendientesAsync(estadoFirma: 100, estadoBiometria: 70);
                Solicitudes = result.Select(s => new SolicitudItemViewModel
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
                Solicitudes.Clear();
            }
            finally
            {
                IsLoading = false;
                StateHasChanged();
            }
        }

        protected void ToggleSelectAll(ChangeEventArgs e)
        {
            var isChecked = e.Value is bool b && b;
            foreach (var item in FilteredSolicitudes)
            {
                item.IsSelected = isChecked;
            }
        }

        protected async Task ReprocesarSeleccionadosAsync()
        {
            var selectedItems = Solicitudes.Where(s => s.IsSelected).ToList();
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
                try
                {
                    item.EstadoReproceso = "Consultando MariaDB...";
                    StateHasChanged();

                    var logResult = await LogApiService.GetAdicionalAsync(item.Solicitud.IdSolicitud);
                    
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

                        bool success = await FirmaApiService.ReprocesarSolicitudAsync(logResult.Adicional!);
                        if (success)
                        {
                            item.EstadoReproceso = "Éxito";
                            item.IsSelected = false; // Auto uncheck on success
                            exitos++;
                            ExitosasHoyCount++; // Incrementamos el contador de exitosas hoy de forma optimista
                        }
                        else
                        {
                            item.EstadoReproceso = "Fallo al reprocesar";
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
                
                await Task.Delay(50);
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

        protected void ClearAlert()
        {
            AlertMessage = "";
        }
    }
}
