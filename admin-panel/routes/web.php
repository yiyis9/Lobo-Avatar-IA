<?php

use App\Http\Controllers\AdminPanelController;
use App\Http\Controllers\AuthenticationController;
use Illuminate\Support\Facades\Route;

Route::redirect('/', '/acceso');
Route::get('/acceso', fn () => view('auth.access'))->name('access');

Route::get('/login', [AuthenticationController::class, 'showLogin'])->name('login');
Route::post('/login', [AuthenticationController::class, 'login'])->middleware('throttle:8,1')->name('login.submit');
Route::get('/registro', [AuthenticationController::class, 'showRegistration'])->name('register');
Route::post('/registro', [AuthenticationController::class, 'register'])->middleware('throttle:8,1')->name('register.submit');
Route::post('/logout', [AuthenticationController::class, 'logout'])->name('logout');

Route::middleware('admin.session')->group(function (): void {
    Route::get('/dashboard', [AdminPanelController::class, 'dashboard'])->name('admin.dashboard');
    Route::get('/preguntas', [AdminPanelController::class, 'questions'])->name('admin.questions');
    Route::get('/preguntas/nueva', [AdminPanelController::class, 'createQuestion'])->name('admin.questions.create');
    Route::post('/preguntas', [AdminPanelController::class, 'storeQuestion'])->name('admin.questions.store');
    Route::get('/preguntas/{id}/editar', [AdminPanelController::class, 'editQuestion'])->whereNumber('id')->name('admin.questions.edit');
    Route::put('/preguntas/{id}', [AdminPanelController::class, 'updateQuestion'])->whereNumber('id')->name('admin.questions.update');
    Route::delete('/preguntas/{id}', [AdminPanelController::class, 'archiveQuestion'])->whereNumber('id')->name('admin.questions.archive');
    Route::get('/solicitudes', [AdminPanelController::class, 'requests'])->name('admin.requests');
    Route::put('/solicitudes/{id}', [AdminPanelController::class, 'decideRequest'])->whereNumber('id')->name('admin.requests.decide');
    Route::get('/usuarios', [AdminPanelController::class, 'users'])->name('admin.users');
    Route::patch('/usuarios/{id}/estado', [AdminPanelController::class, 'setUserState'])->whereNumber('id')->name('admin.users.state');
    Route::get('/perfil', [AdminPanelController::class, 'profile'])->name('admin.profile');
    Route::get('/configuracion', [AdminPanelController::class, 'settings'])->name('admin.settings');
    Route::get('/mantenimiento', [AdminPanelController::class, 'maintenance'])->name('admin.maintenance');
    Route::get('/reportes', [AdminPanelController::class, 'reports'])->name('admin.reports');
    Route::get('/reportes/descargar', [AdminPanelController::class, 'downloadReport'])->name('admin.reports.download');
});
