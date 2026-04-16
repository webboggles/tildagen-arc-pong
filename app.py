import app
import math
import random
from events.input import Buttons, BUTTON_TYPES

try:
    import imu
    HAS_IMU = True
except ImportError:
    HAS_IMU = False

DEG2RAD = 0.01745329

class TildagonApp(app.App):
    def __init__(self):
        self.button_states = Buttons(self)
        self.reset()

    def reset(self):
        # Paddle is an arc segment on the outer circle
        self.paddle_angle = math.pi / 2  # start at bottom
        self.paddle_half_width = 0.5  # radians
        self.paddle_radius = 108
        self.outer_radius = 115

        # Ball - starts stuck to bat
        self.ball_r = 2
        self.ball_stuck = True
        self.ball_speed = 90.0
        self.ball_vx = 0.0
        self.ball_vy = 0.0
        self._place_ball_on_paddle()

        # Brick arcs fill the middle as concentric thin rings (3px thick)
        # leaving a solid inner circle in the centre
        self.bricks = []
        self.inner_core_radius = 20  # solid circle in middle
        brick_thickness = 6
        gap = 1  # spacing between rings
        ring_start = self.inner_core_radius + 4
        ring_end = 65  # leave room before paddle
        colours = [
            (1.0, 0.3, 0.3),
            (1.0, 0.6, 0.2),
            (1.0, 0.9, 0.2),
            (0.4, 1.0, 0.4),
            (0.3, 0.8, 1.0),
            (0.6, 0.4, 1.0),
            (1.0, 0.4, 0.8),
        ]
        r = ring_start
        ring_idx = 0
        while r + brick_thickness <= ring_end:
            r_in = r
            r_out = r + brick_thickness
            # Number of segments scales with radius
            circ = 2 * math.pi * ((r_in + r_out) * 0.5)
            segs = max(6, int(circ / 18))
            seg_size = 2 * math.pi / segs
            colour = colours[ring_idx % len(colours)]
            for i in range(segs):
                a0 = i * seg_size
                a1 = a0 + seg_size * 0.9
                self.bricks.append({
                    'r_in': r_in,
                    'r_out': r_out,
                    'a0': a0,
                    'a1': a1,
                    'colour': colour,
                    'alive': True,
                })
            r = r_out + gap
            ring_idx += 1

        self.score = 0
        self.lives = 3
        self.game_over = False
        self.won = False

    def _place_ball_on_paddle(self):
        # Place ball just inside the paddle, at paddle's current angle
        r = self.paddle_radius - self.ball_r - 4
        self.ball_x = math.cos(self.paddle_angle) * r
        self.ball_y = math.sin(self.paddle_angle) * r

    def _launch_ball(self):
        # Launch inward from paddle, with slight random angle variation
        inward_angle = self.paddle_angle + math.pi
        jitter = random.uniform(-0.4, 0.4)
        ang = inward_angle + jitter
        self.ball_vx = math.cos(ang) * self.ball_speed
        self.ball_vy = math.sin(ang) * self.ball_speed
        self.ball_stuck = False

    def update(self, delta):
        if self.button_states.get(BUTTON_TYPES["CANCEL"]):
            self.button_states.clear()
            self.minimise()
            return

        if self.button_states.get(BUTTON_TYPES["CONFIRM"]):
            self.button_states.clear()
            if self.game_over or self.won:
                self.reset()
                return
            if self.ball_stuck:
                self._launch_ball()

        if self.game_over or self.won:
            return

        dt = delta * 0.001
        if dt > 0.1:
            dt = 0.1

        # Control paddle with gyro yaw
        if HAS_IMU:
            try:
                gx, gy, gz = imu.gyro_read()
                turn = gz
                if abs(turn) > 3.0:
                    self.paddle_angle += turn * DEG2RAD * dt
            except Exception:
                pass
        else:
            if self.button_states.get(BUTTON_TYPES["LEFT"]):
                self.paddle_angle -= 1.5 * dt
            if self.button_states.get(BUTTON_TYPES["RIGHT"]):
                self.paddle_angle += 1.5 * dt

        # Wrap paddle angle
        while self.paddle_angle > math.pi:
            self.paddle_angle -= 2 * math.pi
        while self.paddle_angle < -math.pi:
            self.paddle_angle += 2 * math.pi

        # If ball stuck, keep it on paddle
        if self.ball_stuck:
            self._place_ball_on_paddle()
            return

        # Move ball
        self.ball_x += self.ball_vx * dt
        self.ball_y += self.ball_vy * dt

        # Ball vs inner solid core - bounce off it
        ball_dist = math.sqrt(self.ball_x * self.ball_x + self.ball_y * self.ball_y)
        if ball_dist < self.inner_core_radius + self.ball_r:
            if ball_dist > 0.001:
                nx = self.ball_x / ball_dist
                ny = self.ball_y / ball_dist
            else:
                nx, ny = 1.0, 0.0
            vdotn = self.ball_vx * nx + self.ball_vy * ny
            if vdotn < 0:
                self.ball_vx -= 2 * vdotn * nx
                self.ball_vy -= 2 * vdotn * ny
            push = self.inner_core_radius + self.ball_r + 0.5
            self.ball_x = nx * push
            self.ball_y = ny * push
            ball_dist = push

        # Ball vs bricks
        ball_angle = math.atan2(self.ball_y, self.ball_x)
        if ball_angle < 0:
            ball_angle_n = ball_angle + 2 * math.pi
        else:
            ball_angle_n = ball_angle

        for b in self.bricks:
            if not b['alive']:
                continue
            if ball_dist + self.ball_r >= b['r_in'] and ball_dist - self.ball_r <= b['r_out']:
                a0 = b['a0']
                a1 = b['a1']
                if a0 <= ball_angle_n <= a1:
                    b['alive'] = False
                    self.score += 10
                    mid_r = (b['r_in'] + b['r_out']) * 0.5
                    if ball_dist > 0.001:
                        nx = self.ball_x / ball_dist
                        ny = self.ball_y / ball_dist
                    else:
                        nx, ny = 1.0, 0.0
                    vdotn = self.ball_vx * nx + self.ball_vy * ny
                    self.ball_vx -= 2 * vdotn * nx
                    self.ball_vy -= 2 * vdotn * ny
                    if ball_dist < mid_r:
                        push = b['r_in'] - self.ball_r - 0.5
                        self.ball_x = nx * push
                        self.ball_y = ny * push
                    else:
                        push = b['r_out'] + self.ball_r + 0.5
                        self.ball_x = nx * push
                        self.ball_y = ny * push
                    break

        # Check win
        any_alive = False
        for b in self.bricks:
            if b['alive']:
                any_alive = True
                break
        if not any_alive:
            self.won = True

        # Ball vs paddle / outer
        ball_dist = math.sqrt(self.ball_x * self.ball_x + self.ball_y * self.ball_y)
        if ball_dist + self.ball_r >= self.paddle_radius:
            ball_angle = math.atan2(self.ball_y, self.ball_x)
            da = ball_angle - self.paddle_angle
            while da > math.pi:
                da -= 2 * math.pi
            while da < -math.pi:
                da += 2 * math.pi

            if abs(da) <= self.paddle_half_width:
                nx = self.ball_x / ball_dist
                ny = self.ball_y / ball_dist
                vdotn = self.ball_vx * nx + self.ball_vy * ny
                if vdotn > 0:
                    self.ball_vx -= 2 * vdotn * nx
                    self.ball_vy -= 2 * vdotn * ny
                    offset = da / self.paddle_half_width
                    tx = -ny
                    ty = nx
                    spin = offset * 30.0
                    self.ball_vx += tx * spin
                    self.ball_vy += ty * spin
                    sp = math.sqrt(self.ball_vx * self.ball_vx + self.ball_vy * self.ball_vy)
                    max_sp = 180.0
                    if sp > max_sp:
                        self.ball_vx = self.ball_vx / sp * max_sp
                        self.ball_vy = self.ball_vy / sp * max_sp
                    push = self.paddle_radius - self.ball_r - 1
                    self.ball_x = nx * push
                    self.ball_y = ny * push
            elif ball_dist >= self.outer_radius:
                self.lives -= 1
                if self.lives <= 0:
                    self.game_over = True
                else:
                    self.ball_stuck = True
                    self.ball_vx = 0
                    self.ball_vy = 0
                    self._place_ball_on_paddle()

    def draw(self, ctx):
        ctx.save()
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()

        # Draw solid inner core
        ctx.rgb(0.5, 0.5, 0.6)
        ctx.begin_path()
        ctx.arc(0, 0, self.inner_core_radius, 0, 2 * math.pi, False)
        ctx.fill()

        # Draw bricks as 3px thick arcs
        ctx.line_width = 3
        for b in self.bricks:
            if not b['alive']:
                continue
            c = b['colour']
            ctx.rgb(c[0], c[1], c[2])
            mid_r = (b['r_in'] + b['r_out']) * 0.5
            ctx.begin_path()
            ctx.arc(0, 0, mid_r, b['a0'], b['a1'], False)
            ctx.stroke()

        # Draw ball
        ctx.rgb(1.0, 1.0, 1.0)
        ctx.begin_path()
        ctx.arc(self.ball_x, self.ball_y, self.ball_r, 0, 2 * math.pi, False)
        ctx.fill()

        # Draw paddle as thick arc
        ctx.rgb(0.2, 1.0, 0.4)
        ctx.line_width = 6
        ctx.begin_path()
        ctx.arc(0, 0, self.paddle_radius,
                self.paddle_angle - self.paddle_half_width,
                self.paddle_angle + self.paddle_half_width,
                False)
        ctx.stroke()

        # HUD
        ctx.rgb(1, 1, 1)
        ctx.font_size = 16
        s = "Score: {}  / {}".format(self.score, self.lives)
        ctx.move_to(-ctx.text_width(s) / 2, -100).text(s)

        if self.ball_stuck and not self.game_over and not self.won:
            ctx.rgb(1, 1, 0.4)
            ctx.font_size = 14
            t = "Press C to launch"
            ctx.move_to(-ctx.text_width(t) / 2, 105).text(t)

        if self.game_over:
            ctx.rgb(1.0, 0.3, 0.3)
            ctx.font_size = 28
            t = "GAME OVER"
            ctx.move_to(-ctx.text_width(t) / 2, 0).text(t)
            ctx.font_size = 16
            ctx.rgb(1, 1, 1)
            t2 = "CONFIRM to restart"
            ctx.move_to(-ctx.text_width(t2) / 2, 25).text(t2)
        elif self.won:
            ctx.rgb(0.3, 1.0, 0.5)
            ctx.font_size = 28
            t = "YOU WIN!"
            ctx.move_to(-ctx.text_width(t) / 2, 0).text(t)
            ctx.font_size = 16
            ctx.rgb(1, 1, 1)
            t2 = "CONFIRM to restart"
            ctx.move_to(-ctx.text_width(t2) / 2, 25).text(t2)

        ctx.restore()

__app_export__ = TildagonApp