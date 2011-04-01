# Copyright 2006 Phil Hassey
# Copyright 2007 Adam Ulvi, Shannon Behrens
#
# This code started life as a part of Phil Hassey's PGU example,
# tilevid5.py.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""This is the game's main module.

It contains the entry point used by the run_game.py script.

"""

import math
import random

from pgu import tilevid, timer
import pygame
from pygame.locals import *
import pygame.mixer
from pygame.mixer import Sound
from pygame.rect import Rect

from data import filepath

__docformat__ = 'restructuredtext'

SCREEN_WIDTH, SCREEN_HEIGHT = 240, 240
TILE_WIDTH, TILE_HEIGHT = 16, 16
SPEED = 2
FPS = 40


class SuperSprite(tilevid.Sprite):

    """This is a common superclass for players and enemies.

    You must define:

      default_image_name
        This is the default image to show for the sprite.

      default_group_name
        This is the default group you're a member of.

      default_agroup_name
        This is the default group of sprites you can run into.

      default_hitcount
        The default amount of life you have.

      collision_damage
        This is the amount of damage you inflict to someone else when
        you run into them.

      animator_func(self)
        You can point this at different functions to do animations.  By
        default, it gets set to default_animator.

    """

    invincible = False
    invincible_time = 5

    def __init__(self, g, t, value, pos=None):
        """Set stuff up.

        g
          The game object.

        t
          The tile the sprite starts on.  Usually this is set using
          leveleditor and codes.  If you pass None, I'll "cope".

        value
          This is PGU's way of passing arbitrary stuff to the
          constructor.

        pos
          If you pass this, I'll use it as the starting spot for the
          sprite.  Otherwise, I'll get it out of t.

        """
        if pos is not None:
            arg = pos
        else:
            arg = t.rect
        tilevid.Sprite.__init__(self, g.images[self.default_image_name], arg)
        self.g = g
        if t is not None:
            g.clayer[t.ty][t.tx] = 0
        g.sprites.append(self)
        self.first_frame = g.frame
        self.origin = pygame.Rect(self.rect)
        self.groups = g.string2groups(self.default_group_name)
        self.agroups = g.string2groups(self.default_agroup_name)
        self.hitcount = self.default_hitcount
        self.blank_image = self.image.copy()
        self.blank_image.fill((0, 0, 0, 1))
        self.animator_func = self.default_animator

    def loop(self, g, s):
        """Call loop_func and animator_func."""
        self.loop_func()
        self.animator_func()
        self.constrain_sprites()

    def loop_func(self):
        """This gets called every loop.

        Take care of things like controls, etc.

        """
        pass

    def constrain_sprites(self):
        """Wipe sprites who go off the board.

        Don't wipe off the enemies who just got spawned one row above
        the view.  We don't need to special case the player because he
        can't actually move off the board.

        """
        rect = self.rect
        view = self.g.view
        if (rect.left < view.left or
            rect.right > view.right or
            rect.top > view.bottom or
            rect.bottom < view.top - TILE_HEIGHT):
            self.remove_sprite_safely()

    def hit(self, g, s, hitee):
        self.hit_func(hitee)

    def hit_func(self, hitee):
        """We just got hit by hitee.

        Extend this method as necessary.

        """
        if self.invincible or hitee.invincible:
            return
        self.hitcount -= hitee.collision_damage
        if self.hitcount > 0:
            self.damaged_func()
        else:
            self.destroyed_func()

    def damaged_func(self):
        """This gets called when the SuperSprite is damaged.

        Extend this method as necessary.

        """
        self.animator_func = self.create_damaged_animator()

    def destroyed_func(self):
        """This gets called when the SuperSprite is destroyed.

        Extend this method as necessary.

        """
        self.animator_func = self.create_destroyed_animator()

    def after_destroyed_func(self):
        """Now safely get rid of the sprite."""
        self.remove_sprite_safely()

    def default_animator(self):
        """This is the default animator."""
        self.image = self.g.images[self.default_image_name][0]

    def create_damaged_animator(self):

        """This is the animator for when the SuperSprite is damaged.

        This function returns a closure.

        """

        def f():
            f.count -= 1
            if f.count % 3 == 0:
                self.image = self.blank_image
            else:
                self.default_animator()
            if f.count <= 0:
                self.animator_func = self.default_animator
                self.invincible = False

        def task():
            self.invincible = True

        if self.default_group_name == 'player':
            play_wav('damaged.wav')
        f.count = self.invincible_time
        self.g.post_frame_tasks.append(task)
        return f

    def create_destroyed_animator(self):

        """This is the animator for when the enemy is damaged.

        And by "damaged" I mean exploding.  It provides _closure_.

        """

        def f():
            f.count += 1
            n = f.count / 3
            if n <= 2:
                self.image = self.g.images['explosion-%s' % n][0]
            else:
                self.after_destroyed_func()

        def task():
            self.invincible = True

        play_wav('explosion.wav')
        f.count = 0
        self.g.post_frame_tasks.append(task)
        return f

    def create_alternating_animator(self, num_images, frames_per_image,
                                    image_name_format):

        """Treat a bunch of images like an animated gif.

        Return a closure.

        num_images
          The total number of images in the animation sequence.

        frames_per_image
          How many frames should each of the images in the series get?

        image_name_format
          This is a string like "image-%s".

        """

        def f():
            n = (self.uptime() % total_frames) / frames_per_image
            self.image = self.g.images[image_name_format % n][0]

        total_frames = num_images * frames_per_image
        return f

    def uptime(self):
        """How many frames have we been alive for?"""
        return self.g.frame - self.first_frame

    def remove_sprite_safely(self):
        """Remove self from self.g.sprites.

        Don't die if it's no longer there.  This is needed in certain
        situations such as when a shot hits two targets at the same
        time.  Each hit will cause the shot to delete itself, and the
        second time will cause an exception.

        """
        try:
            self.g.sprites.remove(self)
        except ValueError:
            pass


class Helicopter(SuperSprite):

    """This is a common superclass for helicopters.

    You must define:

      blade_image_format
        This is something like 'player-%s'.

    """

    def __init__(self, g, t, value):
        self.default_animator = self.create_alternating_animator(
            2, 2, self.blade_image_format)
        SuperSprite.__init__(self, g, t, value)


class Player(Helicopter):

    """This is the main class for the good guy."""

    default_image_name = 'player_helicopter-0'
    default_group_name = 'player'
    default_agroup_name = 'enemy'
    default_hitcount = 10
    collision_damage = 2
    blade_image_format = 'player_helicopter-%s'
    invincible_time = 45

    def __init__(self, g, t, value):
        Helicopter.__init__(self, g, t, value)
        g.player = self
        self.score = 0

    def loop_func(self):
        if self.g.view.y >= TILE_HEIGHT:
            self.rect.y -= SPEED
        else:
            if not hasattr(self, 'red_alert'):
                self.red_alert = play_wav('red_alert.wav', -1)  # Repeat.
            self.handle_done()
        keys = pygame.key.get_pressed()
        dx, dy = 0, 0
        if keys[K_UP]:
            dy -= 1
        if keys[K_DOWN]:
            dy += 1
        if keys[K_LEFT]:
            dx -= 1
        if keys[K_RIGHT]:
            dx += 1
        self.rect.x += dx * 5
        self.rect.y += dy * 5
        self.rect.clamp_ip(self.g.view)
        if keys[K_SPACE] and self.g.frame % 4 == 0:
            pos = (self.rect.centerx - 6, self.rect.top - 2)
            Artillery(self, pos=pos, angle=(0.5 * math.pi), image_name="shot")
            play_wav('shooting.wav', 0, 20)  # Keep it short.

    def destroyed_func(self):
        """Ah, boo!"""
        Helicopter.destroyed_func(self)
        self.g.game_over()

    def handle_done(self):
        """Check to see if the game is done.

        We're done once the screen stops moving and all the enemies left
        have been marked as invincible (i.e. burning turrets).

        """
        for s in self.g.sprites:
            if s.default_group_name == 'enemy' and not s.invincible:
                break
        else:
            self.g.winner()


class EnemyHeli(Helicopter):

    default_image_name = 'enemy_helicopter-0'
    default_group_name = 'enemy'
    default_agroup_name = 'player'
    default_hitcount = 1
    collision_damage = 1
    blade_image_format = 'enemy_helicopter-%s'

    def __init__(self, g, t, value):
        """Setup the move function.

        value
          This should be ``{'move': move_func}`` where move is a
          function to handle the type of movement the enemy will do.

        """
        Helicopter.__init__(self, g, t, value)
        self.move = value['move']

    def loop_func(self):
        self.move(self)
        if random.randint(0, 30) == 0 and self.hitcount > 0:
            pos = (self.rect.centerx - 6, self.rect.bottom + 2)
            Artillery(self, pos=pos)

    def destroyed_func(self):
        Helicopter.destroyed_func(self)
        self.g.player.score += 500


class GunTurret(SuperSprite):

    default_image_name = "gun_turret"
    default_group_name = "enemy"
    default_agroup_name = "player"
    default_hitcount = 3
    collision_damage = 1
    shot_image = "gun_bullet"
    shot_speed = 5.5
    shot_freq = 20

    def __init__(self, g, t, value):
        """Save the original image."""
        SuperSprite.__init__(self, g, t, value)
        self.orig_image = self.image
        self.orig_center = self.rect.center

    def loop_func(self):
        s_rect = self.rect
        p_rect = self.g.player.rect
        dx = p_rect.x - s_rect.x
        dy = p_rect.y - s_rect.y
        self.rad = math.atan2(-dy, dx)
        pos = (self.rect.centerx, self.rect.centery)
        if self.uptime() % self.shot_freq == 0 and self.hitcount > 0:
            Artillery(self, pos=pos, angle=self.rad,
                      speed=self.shot_speed,
                      image_name=self.shot_image,
                      collision_damage=self.collision_damage)

    def default_animator(self):
        """Have the turret track the player."""
        self.image = pygame.transform.rotate(self.orig_image,
                                             rad_to_ccw(self.rad))
        self.rect = self.image.get_rect()
        self.rect.center = self.orig_center

    def destroyed_func(self):
        SuperSprite.destroyed_func(self)
        self.g.player.score += 1500

    def after_destroyed_func(self):
        """Draw a destroyed image instead of removing from screen."""
        self.animator_func = self.create_alternating_animator(
            2, 4, "turret_destroyed-%s")


class MissleTurret(GunTurret):

    default_image_name = "missle_turret"
    shot_image = "missle"
    shot_speed = 5
    shot_freq = 30
    collision_damage = 2


# These are the various enemy movement handlers.

def move_line(sprite):
    sprite.rect.y += SPEED


def move_sine(sprite):
    sprite.rect.y += SPEED
    sprite.rect.x = (sprite.origin.x +
                     65 * math.sin(sprite.uptime() / 10.0))


def move_circle(sprite):
    sprite.rect.x = (sprite.origin.x +
                     50 * math.cos(sprite.uptime() / 10.0))
    sprite.rect.y = (sprite.origin.y +
                     50 * math.sin(sprite.uptime() / 10.0))


class Artillery(SuperSprite):

    """SuperSprite is awesome. It's, in fact, super."""

    def __init__(self, shooter, pos, angle=(1.5 * math.pi),
                 speed=6, image_name="enemy_shot", collision_damage=1):
        self.default_image_name = image_name
        self.default_group_name = shooter.default_group_name
        self.default_agroup_name = shooter.default_agroup_name
        self.default_hitcount = 1
        self.collision_damage = collision_damage
        SuperSprite.__init__(self, shooter.g, t=None, value=None, pos=pos)
        orig_center = self.rect.center
        self.image = pygame.transform.rotate(self.image, rad_to_ccw(angle))
        self.rect = self.image.get_rect()
        self.rect.center = orig_center
        self.dx = math.cos(angle) * speed
        self.dy = -math.sin(angle) * speed

    def loop_func(self):
        self.rect.x += self.dx
        self.rect.y += self.dy - SPEED

    def default_animator(self):
        """Unlike the superclass, don't reset the image."""
        pass

    def destroyed_func(self):
        """When the bullet hits, don't make a big deal about it."""
        self.after_destroyed_func()


def rad_to_ccw(rad):
    """Convert radians to a counterclockwise angle in degrees."""
    return math.degrees(rad) + 90


def tile_block(g, t, a):
    c = t.config
    if (c['top'] == 1 and
        a._rect.bottom <= t._rect.top and
        a.rect.bottom > t.rect.top):
        a.rect.bottom = t.rect.top
    if (c['left'] == 1 and
        a._rect.right <= t._rect.left and
        a.rect.right > t.rect.left):
        a.rect.right = t.rect.left
    if (c['right'] == 1 and
        a._rect.left >= t._rect.right and
        a.rect.left < t.rect.right):
        a.rect.left = t.rect.right
    if (c['bottom'] == 1 and
        a._rect.top >= t._rect.bottom and
        a.rect.top < t.rect.bottom):
        a.rect.top = t.rect.bottom


def play_wav(name, *args):
    """This is a convenience method to play a wav.

    *args
      These are passed to play.

    Return the sound object.

    """
    s = Sound(filepath(name))
    s.play(*args)
    return s


class SuperTilevid(tilevid.Tilevid):

    """This is the superclass of all the different Tilevids."""

    image_data = []
    codes_data = {}
    tile_data = {}
    level_file = "level-0.tga"  # If nothing else, use level-0.
    tiles_file = "tiles.tga"

    def __init__(self, screen=None, my_timer=None, prev_vid=None):
        """Set everything up.

        If you have an existing vid, you can pass that instead of
        passing screen and my_timer.

        """
        if prev_vid is not None:
            if screen is None:
                screen = prev_vid.screen
            if my_timer is None:
                my_timer = prev_vid.timer
        tilevid.Tilevid.__init__(self)
        self.screen = screen
        self.timer = my_timer
        self.view.w, self.view.h = SCREEN_WIDTH, SCREEN_HEIGHT
        self.frame = 0
        self.tga_load_tiles(filepath(self.tiles_file),
                            (TILE_WIDTH, TILE_HEIGHT),
                            self.tile_data)
        self.tga_load_level(filepath(self.level_file), bg=True)
        self.bounds = pygame.Rect(TILE_WIDTH, TILE_HEIGHT,
                                  (len(self.tlayer[0]) - 2) * TILE_WIDTH,
                                  (len(self.tlayer) - 2) * TILE_HEIGHT)
        self.load_images(self.image_data)
        self.font = pygame.font.SysFont('helvetica', 16)
        self.next_vid = None

    def run(self):
        """This is the main loop.

        The run method can be used to transition to another Tilevid by
        returning a new instance.  If you return None, that's it for the
        game.  To make use of this feature, set self.next_tilevid, and
        I'll return it at the appropriate time.

        During the run(), anyone can add to self.post_frame_tasks.  This
        is a list of functions that will get run after everything else
        for this frame is taken care of.  It gets set to [] on every
        frame.

        """
        self.quit = False
        self.pause = False
        while not self.quit:
            self.post_frame_tasks = []
            for e in pygame.event.get():
                if e.type is QUIT:
                    self.quit = True
                elif e.type is KEYDOWN and e.key == K_ESCAPE:
                    self.quit = True
                elif e.type is KEYDOWN and e.key == K_F9:
                    pygame.display.toggle_fullscreen()
                else:
                    self.handle_event(e)
            if not self.pause:
                self.pre_loop()
                self.loop()
                self.screen.fill((0, 0, 0))
                self.paint(self.screen)
                self.post_paint()
                for f in self.post_frame_tasks:
                    f()
                pygame.display.flip()
                self.frame += 1
            self.timer.tick()
            if self.next_vid is not None:
                return self.next_vid
        return None

    def handle_event(self, e):
        """Handle any uncaught events."""
        pass

    def pre_loop(self):
        """This gets called before self.loop.

        Now might be a good time to call self.run_codes.

        """
        pass

    def post_paint(self):
        """Do any additional painting necessary.

        For instance, you might want to draw a scoreboard.

        """
        pass


class BasicImageTilevid(SuperTilevid):

    """This is the most basic Tilevid we have.  It just shows an image.

    You must define:

      next_vid_class_name
        This is the name of the next Tilevid to display after this one
        exits.  I have to use a name in order to avoid circular
        dependencies.

      default_image_name
        The default image name to load.

    """

    def __init__(self, *args, **kargs):
        self.image_data = [(self.default_image_name,
                            filepath('%s.tga' % self.default_image_name),
                            (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))]
        SuperTilevid.__init__(self, *args, **kargs)

    def handle_event(self, e):
        if e.type is KEYDOWN and e.key == K_RETURN:
            self.transition()

    def post_paint(self):
        img = self.images[self.default_image_name][0]
        self.screen.blit(img, (0, 0))

    def transition(self):
        self.next_vid = globals()[self.next_vid_class_name](prev_vid=self)


class SplashScreenTilevid(BasicImageTilevid):

    next_vid_class_name = "LevelTilevid"
    default_image_name = "splash_screen"


class GameOverTilevid(BasicImageTilevid):

    next_vid_class_name = "SplashScreenTilevid"
    default_image_name = "game_over"


class WinnerTilevid(BasicImageTilevid):

    next_vid_class_name = "SplashScreenTilevid"
    default_image_name = "winner"


class LevelTilevid(SuperTilevid):

    """This is the Tilevid for a real, live level."""

    helicopter_bounds = (6, 1, 26, 31)
    image_data = [
        ('shot', filepath('shot.tga'), (1, 2, 6, 4)),
        ('gun_turret', filepath('gun_turret.tga'), (0, 0, 32, 32)),
        ('gun_bullet', filepath('gun_bullet.tga'), (0, 0, 16, 8)),
        ('missle_turret', filepath('missle_turret.tga'), (0, 0, 32, 35)),
        ('missle', filepath('missle.tga'), (0, 0, 9, 29)),
        ('enemy_shot', filepath('enemy_shot.tga'), (0, 0, 5, 5)),
    ]
    for i in range(2):
        image_data.extend([
            ('player_helicopter-%s' % i,
             filepath('player_helicopter-%s.tga' % i),
             helicopter_bounds),
            ('enemy_helicopter-%s' % i,
             filepath('enemy_helicopter-%s.tga' % i),
             helicopter_bounds),
            ('turret_destroyed-%s' % i,
             filepath('turret_destroyed-%s.tga' % i),
             (0, 0, 32, 32))
        ])
    for i in range(3):
        image_data.append(
            ('explosion-%s' % i, filepath('explosion-%s.tga' % i),
             (0, 0, 32, 32))
        )

    codes_data = {
        1: (Player, None),
        2: (EnemyHeli, {'move': move_line}),
        3: (EnemyHeli, {'move': move_sine}),
        4: (EnemyHeli, {'move': move_circle}),
        5: (GunTurret, None),
        6: (MissleTurret, None)
    }

    tile_data = {
        # We don't currently have a real block.
        # 0x1: ('player', tile_block,
        #        {'top': 1, 'bottom': 1, 'left': 1, 'right': 1})
    }

    def __init__(self, screen=None, my_timer=None, prev_vid=None, level=0):
        """Start at the bottom of the level."""
        self.level = level
        self.level_file = "level-%s.tga" % level
        SuperTilevid.__init__(self, screen, my_timer, prev_vid)
        self.view.x = 0
        self.view.y = 183 * TILE_HEIGHT
        self.run_codes(self.codes_data, (0, 183, 17, 17))
        self.pause = False

    def handle_event(self, e):
        if e.type is KEYDOWN and e.key == K_RETURN:
            self.pause ^= 1

    def pre_loop(self):
        """Move the view.  Run the codes."""
        self.view.y -= SPEED
        self.run_codes(self.codes_data,
            (0, self.view.top / TILE_HEIGHT - 1, 17, 1))

    def post_paint(self):
        self.draw_scoreboard()

    def draw_scoreboard(self):

        # Draw the score.

        img = self.font.render('%05d' % self.player.score, 1, (0, 0, 0))
        self.screen.blit(img, (0 + 1, SCREEN_HEIGHT - img.get_height() + 1))
        img = self.font.render('%05d' % self.player.score, 1, (255, 255, 255))
        self.screen.blit(img, (0, SCREEN_HEIGHT - img.get_height()))

        # Add the hits remaining bar.

        hits = self.font.render("#" * self.player.hitcount, 1, (0, 0, 0))
        self.screen.blit(hits, (SCREEN_WIDTH - hits.get_width() + 1,
                                SCREEN_HEIGHT - hits.get_height() + 1))
        hits = self.font.render("#" * self.player.hitcount, 1, (255, 0, 0))
        self.screen.blit(hits, (SCREEN_WIDTH - hits.get_width(),
                                SCREEN_HEIGHT - hits.get_height()))

    def game_over(self):
        """Change self.next_vid."""
        self.next_vid = GameOverTilevid(prev_vid=self)

    def winner(self):
        """Change self.next_vid."""
        self.next_vid = WinnerTilevid(prev_vid=self)


def main():
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), SWSURFACE)
    my_timer = timer.Timer(FPS)
    pygame.font.init()
    pygame.mixer.init(44100, -16, 2, 1024)  # Big buffer for Windows.
    next_vid = SplashScreenTilevid(screen, my_timer)
    while True:
        next_vid = next_vid.run()
        pygame.mixer.stop()                 # Kill any music left running.
        if next_vid is None:
            break
