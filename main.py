import pygame
import numpy as np
from scipy.signal import butter, lfilter
import sounddevice as sd
import piano_lists as pl

# Inicialización de Pygame
pygame.init()
pygame.mixer.set_num_channels(50)

# Configuración de audio
DURACION = 1.0  # Duración del sonido en segundos
FS = 44100  # Frecuencia de muestreo

font = pygame.font.SysFont('Verdana', 30, bold=True)
medium_font = pygame.font.SysFont('Verdana', 20)
small_font = pygame.font.SysFont('Verdana', 10)
real_small_font = pygame.font.SysFont('Verdana', 10)

# Configuración de la ventana
fps = 60
timer = pygame.time.Clock()
WIDTH = 52 * 35
HEIGHT = 400
screen = pygame.display.set_mode([WIDTH, HEIGHT])
pygame.display.set_caption("Diana's Python")

# Listas para almacenar los sonidos generados
white_sounds = []
black_sounds = []

# Listas para las notas activas
active_whites = []
active_blacks = []

# Octavas iniciales
left_oct = 4
right_oct = 5

# Cargar las notas desde piano_lists
left_hand = pl.left_hand
right_hand = pl.right_hand
piano_notes = pl.piano_notes
white_notes = pl.white_notes
black_notes = pl.black_notes
black_labels = pl.black_labels

def filtro_paso_bajo(signal, cutoff=5000, fs=FS, order=5):
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return lfilter(b, a, signal)

def generar_sonido(frecuencia, duracion=DURACION, fs=FS, tipo_onda='seno'):
    # 🔹 Aumentar la duración en notas graves (< C3)
    if frecuencia < 130:  # Menos de C3
        duracion *= 5  # Quintuplicar la duración para capturar mejor los ciclos

    t = np.linspace(0, duracion, int(fs * duracion), False)

    # Generación de la forma de onda
    if tipo_onda == 'seno':
        onda = np.sin(2 * np.pi * frecuencia * t)
    elif tipo_onda == 'cuadrada':
        onda = np.sign(np.sin(2 * np.pi * frecuencia * t))
    elif tipo_onda == 'triangular':
        onda = 2 * np.abs(2 * (t * frecuencia - np.floor(t * frecuencia + 0.5))) - 1
    elif tipo_onda == 'sierra':
        onda = 2 * (t * frecuencia - np.floor(t * frecuencia + 0.5))
    else:
        raise ValueError("Tipo de onda no soportado")

    # Normalizar la amplitud para mantener volumen constante
    onda = onda / np.max(np.abs(onda))

    # 🔹 Aumentar volumen en graves extremos
    if frecuencia < 65:  # Para notas debajo de C2
        factor_compensacion = 10.0  # Amplificación extrema
    elif frecuencia < 130:  # Para notas entre C2 y C3
        factor_compensacion = 6.0  
    elif frecuencia < 260:  # C4 y C3
        factor_compensacion = 2.5  
    else:
        factor_compensacion = 1.0  

    onda *= factor_compensacion

    # 🔹 Ajuste de Envolvente (MUY lento en graves)
    if frecuencia < 65:
        envolvente = np.exp(-0.2 * t / duracion)  # Decaimiento ultra lento
    elif frecuencia < 130:
        envolvente = np.exp(-0.5 * t / duracion)  
    elif frecuencia < 500:
        envolvente = np.exp(-2 * t / duracion)  
    else:
        envolvente = np.exp(-5 * t / duracion)  

    # Aplicar envolvente
    onda *= envolvente

    # 🔹 Generar MUCHAS más muestras en graves profundos
    if frecuencia < 130:
        nueva_longitud = int(len(onda) * 8)  # Octuplicar la resolución
        onda = np.interp(np.linspace(0, len(onda), nueva_longitud), np.arange(len(onda)), onda)

    # 🔹 NO aplicar filtro paso bajo en notas menores a C3
    if tipo_onda in ['cuadrada', 'sierra'] and frecuencia > 260:
        cutoff_dinamico = max(3000, frecuencia * 4)  
        onda = filtro_paso_bajo(onda, cutoff=cutoff_dinamico, fs=fs)

    return onda

# 🔹 Función para reproducir sonido sin cortes en sounddevice
def reproducir_sonido(onda):
    if len(onda) > 0:
        sd.play(onda, FS, blocking=True)  # Asegurar que el sonido se reproduce correctamente


# Función para calcular la frecuencia de una nota
def calcular_frecuencia(nota):
    base_frecuencia = {'C': 261.63, 'C#': 277.18, 'D': 293.66, 'D#': 311.13, 'E': 329.63,
                       'F': 349.23, 'F#': 369.99, 'G': 392.00, 'G#': 415.30, 'A': 440.00,
                       'A#': 466.16, 'B': 493.88}
    nombre_nota, octava = nota[:-1], int(nota[-1])
    if nombre_nota in base_frecuencia:
        return base_frecuencia[nombre_nota] * (2 ** (octava - 4))
    return 0

# Generar los sonidos de las teclas blancas y negras
for nota in white_notes:
    frecuencia = calcular_frecuencia(nota)
    if frecuencia > 0:
        sonido = generar_sonido(frecuencia)
        white_sounds.append(sonido)

for nota in black_notes:
    frecuencia = calcular_frecuencia(nota)
    if frecuencia > 0:
        sonido = generar_sonido(frecuencia)
        black_sounds.append(sonido)

# Función para mezclar sonidos
def mezclar_sonidos(sonidos):
    mezcla = np.sum(sonidos, axis=0)
    mezcla /= np.max(np.abs(mezcla))  # Normaliza la mezcla
    return mezcla

# Función para reproducir múltiples notas
def reproducir_notas(notas):
    sonidos = []
    for nota in notas:
        if '#' in nota:  # Nota negra
            index = black_labels.index(nota)
            if index < len(black_sounds):
                sonidos.append(black_sounds[index])
        else:  # Nota blanca
            index = white_notes.index(nota)
            if index < len(white_sounds):
                sonidos.append(white_sounds[index])
    if sonidos:
        sonido_mezclado = mezclar_sonidos(sonidos)
        sd.play(sonido_mezclado, FS)

# Actualizar `active_whites` y `active_blacks` cuando una tecla es presionada
def actualizar_teclas_activas(nota):
    if '#' in nota:
        index = black_labels.index(nota)
        active_blacks.append([index, 10])  # Duración de la animación en frames
    else:
        index = white_notes.index(nota)
        active_whites.append([index, 10])

# Función para dibujar el piano
def draw_piano(whites, blacks):
    white_rects = []
    for i in range(len(white_notes)):
        rect = pygame.draw.rect(screen, 'white', [i * 35, HEIGHT - 300, 35, 300], 0, 2)
        white_rects.append(rect)
        pygame.draw.rect(screen, 'black', [i * 35, HEIGHT - 300, 35, 300], 2, 2)
        key_label = small_font.render(white_notes[i], True, 'black')
        screen.blit(key_label, (i * 35 + 3, HEIGHT - 20))
    
    skip_count = 0
    last_skip = 2
    skip_track = 2
    black_rects = []
    for i in range(len(black_notes)):
        rect = pygame.draw.rect(screen, 'black', [23 + (i * 35) + (skip_count * 35), HEIGHT - 300, 24, 200], 0, 2)
        for q in range(len(blacks)):
            if blacks[q][0] == i:
                if blacks[q][1] > 0:
                    pygame.draw.rect(screen, 'green', [23 + (i * 35) + (skip_count * 35), HEIGHT - 300, 24, 200], 2, 2)
                    blacks[q][1] -= 1
        
        key_label = real_small_font.render(black_labels[i], True, 'white')
        screen.blit(key_label, (25 + (i * 35) + (skip_count * 35), HEIGHT - 120))
        black_rects.append(rect)
        skip_track += 1
        if last_skip == 2 and skip_track == 3:
            last_skip = 3
            skip_track = 0
            skip_count += 1
        elif last_skip == 3 and skip_track == 2:
            last_skip = 2
            skip_track = 0
            skip_count += 1

    return white_rects, black_rects, whites, blacks
# Función para dibujar las manos
def draw_hands(rightOct, leftOct, rightHand, leftHand):
    # Dibuja la mano izquierda
    pygame.draw.rect(screen, 'blue', [(leftOct * 245) - 175, HEIGHT - 60, 245, 30], 0, 4)
    pygame.draw.rect(screen, 'white', [(leftOct * 245) - 175, HEIGHT - 60, 245, 30], 4, 4)
    text = small_font.render(leftHand[0], True, 'white')
    screen.blit(text, ((leftOct * 245) - 165, HEIGHT - 55))
    text = small_font.render(leftHand[2], True, 'white')
    screen.blit(text, ((leftOct * 245) - 130, HEIGHT - 55))
    text = small_font.render(leftHand[4], True, 'white')
    screen.blit(text, ((leftOct * 245) - 95, HEIGHT - 55))
    text = small_font.render(leftHand[5], True, 'white')
    screen.blit(text, ((leftOct * 245) - 60, HEIGHT - 55))
    text = small_font.render(leftHand[7], True, 'white')
    screen.blit(text, ((leftOct * 245) - 25, HEIGHT - 55))
    text = small_font.render(leftHand[9], True, 'white')
    screen.blit(text, ((leftOct * 245) + 10, HEIGHT - 55))
    text = small_font.render(leftHand[11], True, 'white')
    screen.blit(text, ((leftOct * 245) + 45, HEIGHT - 55))
    text = small_font.render(leftHand[1], True, 'orange')
    screen.blit(text, ((leftOct * 245) - 148, HEIGHT - 55))
    text = small_font.render(leftHand[3], True, 'orange')
    screen.blit(text, ((leftOct * 245) - 113, HEIGHT - 55))
    text = small_font.render(leftHand[6], True, 'orange')
    screen.blit(text, ((leftOct * 245) - 43, HEIGHT - 55))
    text = small_font.render(leftHand[8], True, 'orange')
    screen.blit(text, ((leftOct * 245) - 8, HEIGHT - 55))
    text = small_font.render(leftHand[10], True, 'orange')
    screen.blit(text, ((leftOct * 245) + 27, HEIGHT - 55))

    # Dibuja la mano derecha
    pygame.draw.rect(screen, 'blue', [(rightOct * 245) - 175, HEIGHT - 60, 245, 30], 0, 4)
    pygame.draw.rect(screen, 'white', [(rightOct * 245) - 175, HEIGHT - 60, 245, 30], 4, 4)
    text = small_font.render(rightHand[0], True, 'white')
    screen.blit(text, ((rightOct * 245) - 165, HEIGHT - 55))
    text = small_font.render(rightHand[2], True, 'white')
    screen.blit(text, ((rightOct * 245) - 130, HEIGHT - 55))
    text = small_font.render(rightHand[4], True, 'white')
    screen.blit(text, ((rightOct * 245) - 95, HEIGHT - 55))
    text = small_font.render(rightHand[5], True, 'white')
    screen.blit(text, ((rightOct * 245) - 60, HEIGHT - 55))
    text = small_font.render(rightHand[7], True, 'white')
    screen.blit(text, ((rightOct * 245) - 25, HEIGHT - 55))
    text = small_font.render(rightHand[9], True, 'white')
    screen.blit(text, ((rightOct * 245) + 10, HEIGHT - 55))
    text = small_font.render(rightHand[11], True, 'white')
    screen.blit(text, ((rightOct * 245) + 45, HEIGHT - 55))
    text = small_font.render(rightHand[1], True, 'orange')
    screen.blit(text, ((rightOct * 245) - 148, HEIGHT - 55))
    text = small_font.render(rightHand[3], True, 'orange')
    screen.blit(text, ((rightOct * 245) - 113, HEIGHT - 55))
    text = small_font.render(rightHand[6], True, 'orange')
    screen.blit(text, ((rightOct * 245) - 43, HEIGHT - 55))
    text = small_font.render(rightHand[8], True, 'orange')
    screen.blit(text, ((rightOct * 245) - 8, HEIGHT - 55))
    text = small_font.render(rightHand[10], True, 'orange')
    screen.blit(text, ((rightOct * 245) + 27, HEIGHT - 55))

# Función para dibujar la barra de título
def draw_title_bar():
    instruction_text = medium_font.render('Arriba/Abajo Cambiar la mano izquierda', True, 'black')
    screen.blit(instruction_text, (WIDTH - 600, 10))
    instruction_text2 = medium_font.render('Izquierda/Derecha Cambiar la mano derecha', True, 'black')
    screen.blit(instruction_text2, (WIDTH - 600, 50))
    title_text = font.render('Taller 1, piano en Python!', True, 'white')
    screen.blit(title_text, (298, 18))
    title_text = font.render('Taller 1, piano en Python!', True, 'black')
    screen.blit(title_text, (300, 20))

# Bucle principal
run = True
notas_actuales = []  # Lista para almacenar las notas que se están tocando

while run:
    # Configuración de las teclas para cada mano
    left_dict = {'Z': f'C{left_oct}',
                 'S': f'C#{left_oct}',
                 'X': f'D{left_oct}',
                 'D': f'D#{left_oct}',
                 'C': f'E{left_oct}',
                 'V': f'F{left_oct}',
                 'G': f'F#{left_oct}',
                 'B': f'G{left_oct}',
                 'H': f'G#{left_oct}',
                 'N': f'A{left_oct}',
                 'J': f'A#{left_oct}',
                 'M': f'B{left_oct}'}

    right_dict = {'R': f'C{right_oct}',
                  '5': f'C#{right_oct}',
                  'T': f'D{right_oct}',
                  '6': f'D#{right_oct}',
                  'Y': f'E{right_oct}',
                  'U': f'F{right_oct}',
                  '8': f'F#{right_oct}',
                  'I': f'G{right_oct}',
                  '9': f'G#{right_oct}',
                  'O': f'A{right_oct}',
                  '0': f'A#{right_oct}',
                  'P': f'B{right_oct}'}

    # Limitar la tasa de fotogramas
    timer.tick(fps)

    # Dibujar el fondo
    screen.fill('gray')

    # Dibujar el piano y las notas activas
    white_keys, black_keys, active_whites, active_blacks = draw_piano(active_whites, active_blacks)

    # Dibujar las manos (notas asignadas a cada mano)
    draw_hands(right_oct, left_oct, right_hand, left_hand)

    # Dibujar la barra de título
    draw_title_bar()

    # Manejo de eventos
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False
        if event.type == pygame.KEYDOWN:
            # Mover la mano izquierda (octava)
            if event.key == pygame.K_UP:
                if left_oct < 8:
                    left_oct += 1
            if event.key == pygame.K_DOWN:
                if left_oct > 0:
                    left_oct -= 1

            # Mover la mano derecha (octava)
            if event.key == pygame.K_RIGHT:
                if right_oct < 8:
                    right_oct += 1
            if event.key == pygame.K_LEFT:
                if right_oct > 0:
                    right_oct -= 1
            else:
                key_name = pygame.key.name(event.key).upper()
                if key_name in left_dict:
                    nota = left_dict[key_name]
                elif key_name in right_dict:
                    nota = right_dict[key_name]
                else:
                    nota = None

                if nota:
                    frecuencia = calcular_frecuencia(nota)
                    print(f"Tecla presionada: {nota} - Frecuencia: {frecuencia} Hz")
            # Mapear la tecla presionada a las notas correspondientes
            if event.key == pygame.K_z:
                notas_actuales.append(left_dict['Z'])
            if event.key == pygame.K_s:
                notas_actuales.append(left_dict['S'])
            if event.key == pygame.K_x:
                notas_actuales.append(left_dict['X'])
            if event.key == pygame.K_d:
                notas_actuales.append(left_dict['D'])
            if event.key == pygame.K_c:
                notas_actuales.append(left_dict['C'])
            if event.key == pygame.K_v:
                notas_actuales.append(left_dict['V'])
            if event.key == pygame.K_g:
                notas_actuales.append(left_dict['G'])
            if event.key == pygame.K_b:
                notas_actuales.append(left_dict['B'])
            if event.key == pygame.K_h:
                notas_actuales.append(left_dict['H'])
            if event.key == pygame.K_n:
                notas_actuales.append(left_dict['N'])
            if event.key == pygame.K_j:
                notas_actuales.append(left_dict['J'])
            if event.key == pygame.K_m:
                notas_actuales.append(left_dict['M'])

            if event.key == pygame.K_r:
                notas_actuales.append(right_dict['R'])
            if event.key == pygame.K_5:
                notas_actuales.append(right_dict['5'])
            if event.key == pygame.K_t:
                notas_actuales.append(right_dict['T'])
            if event.key == pygame.K_6:
                notas_actuales.append(right_dict['6'])
            if event.key == pygame.K_y:
                notas_actuales.append(right_dict['Y'])
            if event.key == pygame.K_u:
                notas_actuales.append(right_dict['U'])
            if event.key == pygame.K_8:
                notas_actuales.append(right_dict['8'])
            if event.key == pygame.K_i:
                notas_actuales.append(right_dict['I'])
            if event.key == pygame.K_9:
                notas_actuales.append(right_dict['9'])
            if event.key == pygame.K_o:
                notas_actuales.append(right_dict['O'])
            if event.key == pygame.K_0:
                notas_actuales.append(right_dict['0'])
            if event.key == pygame.K_p:
                notas_actuales.append(right_dict['P'])
        if event.type == pygame.KEYUP:
            # Mapear la tecla liberada a los caracteres correspondientes
            if event.key == pygame.K_z:
                notas_actuales.remove(left_dict['Z'])
            if event.key == pygame.K_s:
                notas_actuales.remove(left_dict['S'])
            if event.key == pygame.K_x:
                notas_actuales.remove(left_dict['X'])
            if event.key == pygame.K_d:
                notas_actuales.remove(left_dict['D'])
            if event.key == pygame.K_c:
                notas_actuales.remove(left_dict['C'])
            if event.key == pygame.K_v:
                notas_actuales.remove(left_dict['V'])
            if event.key == pygame.K_g:
                notas_actuales.remove(left_dict['G'])
            if event.key == pygame.K_b:
                notas_actuales.remove(left_dict['B'])
            if event.key == pygame.K_h:
                notas_actuales.remove(left_dict['H'])
            if event.key == pygame.K_n:
                notas_actuales.remove(left_dict['N'])
            if event.key == pygame.K_j:
                notas_actuales.remove(left_dict['J'])
            if event.key == pygame.K_m:
                notas_actuales.remove(left_dict['M'])

            if event.key == pygame.K_r:
                notas_actuales.remove(right_dict['R'])
            if event.key == pygame.K_5:
                notas_actuales.remove(right_dict['5'])
            if event.key == pygame.K_t:
                notas_actuales.remove(right_dict['T'])
            if event.key == pygame.K_6:
                notas_actuales.remove(right_dict['6'])
            if event.key == pygame.K_y:
                notas_actuales.remove(right_dict['Y'])
            if event.key == pygame.K_u:
                notas_actuales.remove(right_dict['U'])
            if event.key == pygame.K_8:
                notas_actuales.remove(right_dict['8'])
            if event.key == pygame.K_i:
                notas_actuales.remove(right_dict['I'])
            if event.key == pygame.K_9:
                notas_actuales.remove(right_dict['9'])
            if event.key == pygame.K_o:
                notas_actuales.remove(right_dict['O'])
            if event.key == pygame.K_0:
                notas_actuales.remove(right_dict['0'])
            if event.key == pygame.K_p:
                notas_actuales.remove(right_dict['P'])

    # Reproducir las notas actuales
    if notas_actuales:
        reproducir_notas(notas_actuales)

    # Actualizar la pantalla
    pygame.display.flip()

# Salir de Pygame
pygame.quit()