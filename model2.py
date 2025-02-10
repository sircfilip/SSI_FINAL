import pygame
import random
from enum import Enum

from PIL.ImageCms import Direction

# Initialize Pygame
pygame.init()

# Screen settings
WIDTH, HEIGHT = 800, 800
ROAD_LENGTH = 500  # meters
PIXELS_PER_METER = WIDTH / ROAD_LENGTH
FPS = 30

# Car physics settings
MAX_SPEEDS = [20]
ACCELERATION = 2  # m/s²
MAX_DECELERATION = 2  # m/s²
STOP_TIME = 60  # Frames before a car resumes crossing
STOP_SLOWDOWN_DISTANCE = 80 * PIXELS_PER_METER  # Start slowing down 80m before stop
MIN_DISTANCE = 5 * PIXELS_PER_METER  # 5m gap between cars
SPAWN_CLEARANCE = 50 * PIXELS_PER_METER  # 50m clearance for spawning

# Destination options

# Colors
WHITE = (255, 255, 255)
GRAY = (120, 120, 120)
RED = (200, 50, 50)
BLUE = (50, 50, 200)
GREEN = (50, 200, 50)
BLACK = (0, 0, 0)

# Road settings
ROAD_WIDTH = 100
LANE_WIDTH = ROAD_WIDTH // 2
CENTER_X, CENTER_Y = WIDTH // 2, HEIGHT // 2

# Car settings
CAR_WIDTH = 25
CAR_HEIGHT = 15
class Direction(Enum):
    """Possible movement directions."""
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"

class Destination(Enum):
    """Possible movement destinations."""
    LEFT = "left"
    RIGHT = "right"
    BOTTOM = "bottom"

# Stopping positions
STOP_POSITIONS = {
    Direction.RIGHT : CENTER_X - ROAD_WIDTH // 2 - 20,
    Direction.LEFT: CENTER_X + ROAD_WIDTH // 2 + 20,
    Direction.BOTTOM: CENTER_Y - ROAD_WIDTH // 2 - 20,
    Direction.TOP: CENTER_Y + ROAD_WIDTH // 2 + 20,
}

# Initialize font for speed display
pygame.font.init()
font = pygame.font.SysFont(None, 24)




class Car:
    car_counter = 1  # Global counter for assigning unique IDs

    def __init__(self, direction):
        self.id = Car.car_counter  # Assign a unique number to this car
        Car.car_counter += 1

        """Initialize a car with correct lane placement from spawn."""
        self.direction = direction
        self.destination = self.assign_destination()  # ✅ Destination assigned at creation
        self.color = random.choice([RED, BLUE, GREEN])
        self.max_speed = random.choice(MAX_SPEEDS)
        self.speed = self.max_speed
        self.stop_timer = 0  # Timer to manage stopping at the intersection
        self.has_stopped_at_crossroad = False  # Track if the car has stopped
        self.has_turned = False  # Track if the car has already turned

        # Set initial position based on direction
        self.set_initial_position()

    def assign_destination(self):
        """Assign a random valid destination based on the car's entry direction."""
        if self.direction == Direction.RIGHT:
            return random.choice([Destination.RIGHT, Destination.BOTTOM])  # ✅ Right → Right or Bottom
        elif self.direction == Direction.LEFT:
            return random.choice([Destination.LEFT, Destination.BOTTOM])  # ✅ Left → Left or Bottom
        elif self.direction == Direction.TOP:
            return random.choice([Destination.LEFT, Destination.RIGHT])  # ✅ Top → Left or Right
        return None  # Default fallback (should never happen)

    def set_initial_position(self):
        """Set the car's initial position and movement direction based on correct lane placement."""

        if self.direction == Direction.RIGHT:
            # 🚗 Moving LEFT → RIGHT: Spawn in the **BOTTOM** lane (Rightward bottom lane)
            self.x, self.y = -CAR_WIDTH, CENTER_Y + LANE_WIDTH // 2
            self.dx, self.dy, self.angle = 1, 0, 0  # Move right

        elif self.direction == Direction.LEFT:
            # 🚗 Moving RIGHT → LEFT: Spawn in the **TOP** lane (Leftward top lane)
            self.x, self.y = WIDTH + CAR_WIDTH, CENTER_Y - LANE_WIDTH // 2
            self.dx, self.dy, self.angle = -1, 0, 0  # Move left

        elif self.direction == Direction.BOTTOM:
            # 🚗 Moving BOTTOM → TOP: Spawn in the **LEFT** lane of downward road
            self.x, self.y = CENTER_X - LANE_WIDTH // 2, HEIGHT + CAR_HEIGHT
            self.dx, self.dy, self.angle = 0, -1, 90  # Move up

    def can_proceed(self, other_cars):
        """Check if the car can move based on intersection priority rules and cars in the crossroad."""

        # Define 50m proximity range in pixels
        CROSSROAD_RANGE = 50 * PIXELS_PER_METER

        # Filter only cars **inside the crossroad area (within 50m of the center)**
        cars_in_crossroad = [
            car for car in other_cars if
            abs(car.x - CENTER_X) <= CROSSROAD_RANGE or abs(car.y - CENTER_Y) <= CROSSROAD_RANGE
        ]

        # 🚗 **Going Straight (destination = same as direction)**
        if self.destination == self.direction:
            if self.direction == Direction.RIGHT:
                return True  # ✅ Right → Right is always free
            if self.direction == Direction.LEFT:
                # 🚦 Left → Left must check Bottom → Right
                return not any(
                    car.direction == Direction.BOTTOM and car.destination == Destination.RIGHT and car.y >= CENTER_Y
                    for car in cars_in_crossroad
                )

        # 🔽 **Turning Bottom**
        if self.destination == Destination.BOTTOM:
            if self.direction == Direction.LEFT:
                return True  # ✅ Left → Bottom is always free
            if self.direction == Direction.RIGHT:
                # 🚦 Right → Bottom must check Left → Right
                return not any(
                    car.direction == Direction.LEFT and car.destination == Direction.LEFT and car.x <= CENTER_X
                    for car in cars_in_crossroad
                )

        # ◀️ **Turning Left (Bottom → Left)**
        if self.destination == Destination.LEFT:
            # 🚦 Must check Right → Bottom cars before going
            return not any(
                car.direction == Direction.RIGHT and car.destination == Destination.BOTTOM and car.x >= CENTER_X
                for car in cars_in_crossroad
            )

        # ▶️ **Turning Right (Bottom → Right)**
        if self.destination == Destination.RIGHT:
            return True  # ✅ Bottom → Right is always free

        return False  # Default to stop if unsure

    def move(self, other_cars):
        """Apply force-based movement, stop at the intersection, and turn if needed."""

        if self.has_stopped_at_crossroad and not self.can_proceed(other_cars) and not self.has_turned:
            return  # 🚦 Keep waiting if there's a conflict

        # If stopped and already made a decision, begin acceleration
        if self.has_stopped_at_crossroad and self.speed == 0:
            self.speed = min(self.max_speed, ACCELERATION / FPS)  # Start accelerating from rest

        # Handle speed adjustments
        distance_to_target = self.get_distance_to_stop_target()
        self.update_speed(distance_to_target)

        # Stop completely if necessary
        if self.stop_timer > 0:
            self.stop_timer -= 1
            return

        # Handle turning logic after stopping
        self.check_turn()

        # Update position
        self.update_position()

    def check_turn(self):
        """Handle car turning at the intersection."""

        if self.has_turned or self.destination == self.direction:
            return  # ✅ If the car has turned or is going straight, do nothing

        # ✅ Cars turning at the intersection must check their position first
        if self.direction == Direction.RIGHT and self.destination == Destination.BOTTOM:
            if self.x >= CENTER_X - LANE_WIDTH // 2:
                self.turn()

        elif self.direction == Direction.LEFT and self.destination == Destination.BOTTOM:
            if self.x <= CENTER_X + LANE_WIDTH // 2:
                self.turn()

        elif self.direction == Direction.BOTTOM:
            if self.y <= CENTER_Y + LANE_WIDTH // 2:
                self.turn()

    def turn(self):
        """Turn the car based on its assigned destination."""

        self.has_turned = True  # ✅ Mark that this car has turned

        if self.destination == Destination.BOTTOM:
            self.direction = Direction.BOTTOM
            self.dx, self.dy = 0, 1
            self.angle = 90
            self.x = CENTER_X - LANE_WIDTH // 2  # ✅ Align with left lane of downward road

        elif self.destination == Destination.LEFT:
            self.direction = Direction.LEFT
            self.dx, self.dy = -1, 0
            self.angle = 180
            self.y = CENTER_Y - LANE_WIDTH // 2  # ✅ Align with leftward lane

        elif self.destination == Destination.RIGHT:
            self.direction = Direction.RIGHT
            self.dx, self.dy = 1, 0
            self.angle = 0
            self.y = CENTER_Y + LANE_WIDTH // 2  # ✅ Align with rightward lane

    def get_distance_to_stop_target(self):
        """Find the distance to the crossroad stop line only (ignoring other cars)."""

        if self.has_stopped_at_crossroad:
            return 1000  # Large value to prevent stopping again

        # The only stop target is the crossroad stop line
        stop_target = STOP_POSITIONS[self.direction]

        # Return the distance to the stop line
        return abs(stop_target - self.x) if self.dx else abs(stop_target - self.y)

    def calculate_stopping_distance(self):
        """Calculate how far the car needs to stop using physics."""
        if self.speed > 0:
            return (self.speed ** 2) / (2 * MAX_DECELERATION)
        return 0  # If already stopped, no stopping distance needed

    def update_speed(self, distance_to_target):
        """Adjust speed based on the distance to the stop target, ensuring smooth and timely braking."""

        stopping_distance_required = self.calculate_stopping_distance()

        # 🚀 Increase deceleration if we're running out of space to stop
        if stopping_distance_required >= distance_to_target:
            extra_deceleration = min(MAX_DECELERATION * 2, self.speed ** 2 / (2 * distance_to_target))
            self.speed = max(0, self.speed - extra_deceleration / FPS)

        # 🚀 If there's enough space and we're below max speed, accelerate smoothly
        elif self.speed < self.max_speed and distance_to_target > stopping_distance_required * 1.5:
            self.speed = min(self.max_speed, self.speed + ACCELERATION / FPS)

        # ⏹ Stop completely if too close
        if distance_to_target < 1:
            if self.stop_timer == 0:
                self.stop_timer = STOP_TIME
                self.has_stopped_at_crossroad = True
            self.speed = 0  # Full stop

    def update_position(self):
        """Move the car forward based on its speed."""
        self.x += self.dx * self.speed * PIXELS_PER_METER / FPS
        self.y += self.dy * self.speed * PIXELS_PER_METER / FPS


class Simulation:
    def __init__(self):
        """Initialize the simulation."""
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Optimized Traffic Simulation")
        self.clock = pygame.time.Clock()
        self.cars = []
        self.background = self.create_background()


    def can_spawn(self, direction):
        """Check if a new car can spawn with at least 50m clearance."""
        return all(
            car.x > -CAR_WIDTH + SPAWN_CLEARANCE if direction == direction.RIGHT else
            car.x < WIDTH + CAR_WIDTH - SPAWN_CLEARANCE if direction == direction.LEFT else
            car.y > -CAR_HEIGHT + SPAWN_CLEARANCE if direction == direction.TOP else
            car.y < HEIGHT + CAR_HEIGHT - SPAWN_CLEARANCE
            for car in self.cars if car.direction == direction
        )

    def create_background(self):
        """Pre-renders the road with 3 directions (LEFT, RIGHT, BOTTOM) with centered dashed lines."""
        background = pygame.Surface((WIDTH, HEIGHT))
        background.fill(WHITE)  # Fill with background color

        # Draw horizontal road (left to right, full width)
        pygame.draw.rect(background, GRAY, (0, CENTER_Y - ROAD_WIDTH // 2, WIDTH, ROAD_WIDTH))

        # Draw vertical road (bottom only, full width)
        pygame.draw.rect(background, GRAY, (CENTER_X - ROAD_WIDTH // 2, CENTER_Y, ROAD_WIDTH, HEIGHT - CENTER_Y))

        # Draw dashed lane markings for the horizontal road
        for i in range(0, WIDTH, 40):  # Dashed every 40px, with 20px gaps
            pygame.draw.line(background, WHITE, (i, CENTER_Y), (i + 20, CENTER_Y), 2)  # Centered horizontal dashes

        # Draw dashed lane markings for the vertical downward road (only below the intersection)
        for i in range(CENTER_Y, HEIGHT, 40):
            pygame.draw.line(background, WHITE, (CENTER_X, i), (CENTER_X, i + 20), 2)  # Centered vertical dashes

        return background  # Return pre-rendered background

    def spawn_cars(self):
        """Checks each direction separately and spawns cars with independent probabilities, respecting max limits."""
        directions = [Direction.RIGHT, Direction.LEFT]
        spawn_probability = 0.05  # 5% chance per direction
        max_cars_per_direction = 2  # Adjust this value as needed

        # Count cars per direction
        car_counts = {direction: sum(1 for car in self.cars if car.direction == direction) for direction in directions}

        for direction in directions:
            if car_counts[direction] < max_cars_per_direction and self.can_spawn(direction):
                if random.random() < spawn_probability:
                    self.cars.append(Car(direction))

    def run(self):
        """Main simulation loop."""
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False  # Exit loop if the window is closed

            self.screen.blit(self.background, (0, 0))  # Use pre-rendered background

            # Spawn new cars
            self.spawn_cars()

            # Move and draw cars
            for car in self.cars:
                car.move(self.cars)
                self.draw_car(car)

            pygame.display.flip()
            self.clock.tick(30)

        pygame.quit()

    def draw_car(self, car):
        """Draw the car, its speed, and its ID above it."""
        car_surface = pygame.Surface((CAR_WIDTH, CAR_HEIGHT), pygame.SRCALPHA)
        car_surface.fill(car.color)
        rotated_car = pygame.transform.rotate(car_surface, car.angle)
        self.screen.blit(rotated_car, (car.x, car.y - CAR_HEIGHT // 2))

        destination_letter = {
            Destination.LEFT: "L",
            Destination.RIGHT: "R",
            Destination.BOTTOM: "B"
        }.get(car.destination, "?")  # Default to "?" if undefined

        # Display speed above the car
        car_info = font.render(f"{car.id}: {car.speed:.1f} m/s ({destination_letter})", True, BLACK)
        self.screen.blit(car_info, (car.x + 5, car.y - 25))

        # Display car ID above the car
        id_text = font.render(f"#{car.id}", True, BLACK)
        self.screen.blit(id_text, (car.x + 5, car.y - 40))  # Shifted higher to avoid overlap



if __name__ == "__main__":
    Simulation().run()