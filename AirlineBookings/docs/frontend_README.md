# AirlineBookings Frontend Documentation

This is a React-based frontend that acts as an intelligent, chat-driven airline booking interface. 

## Main Files

### `api.js`
- **What it does:** Talks to the Python backend. Contains functions to log in, fetch bookings, and send chat messages.
- **Input (IP):** Text strings (like "Find flights to Delhi"), user credentials.
- **Output (OP):** JSON responses from the server containing chat replies and UI "cards" (like flight options or a seat map).

### `App.jsx` & `main.jsx`
- **What they do:** The entry points of the React application. `App.jsx` handles routing between the login screen, booking history, and the main chat interface.

### `styles.css`
- **What it does:** Contains all the styling for the chat bubbles, flight cards, seat maps, and layout.

## Components (`src/components/`)

### `ChatApp.jsx`
- **What it does:** The main chat window. It manages the conversation history, scrolling, and showing the progress rail (Search -> Select -> Passengers...).
- **Input (IP):** User typing in the text box.
- **Output (OP):** Renders a list of `ChatBubble` components.

### `ChatBubble.jsx`
- **What it does:** Represents a single turn in the conversation (either the user's message or the AI's reply).
- **Input (IP):** Text content and a list of structured "cards" returned by the AI.
- **Output (OP):** Renders the chat text and dynamically renders the correct cards (like flight options or seat maps) using `CardRenderer`.

### `cards/CardRenderer.jsx`
- **What it does:** A switchboard. It looks at the type of card the AI returned (e.g., `flight_options`) and renders the specific UI component for it.
- **Input (IP):** A card object `{type: "flight_options", data: {...}}`.
- **Output (OP):** Renders a specific React component (like `FlightOptionsCard`).

### `cards/FlightOptionsCard.jsx`
- **What it does:** Shows a list of available flights with prices and times.
- **Input (IP):** Array of flight data (airline, price, duration).
- **Output (OP):** A clickable list. When clicked, it tells the chat "I pick this flight".

### `cards/SeatMapCard.jsx`
- **What it does:** Shows the airplane layout visually so the user can pick a seat.
- **Input (IP):** Seat layout array (rows, columns, available/taken status).
- **Output (OP):** User clicks a seat, which sends a message back to the AI (e.g., "Select seat 4A").

### `cards/PassengerListCard.jsx`
- **What it does:** Shows the passengers added so far.
- **Input (IP):** Array of passenger details (name, fare type).
- **Output (OP):** Visual summary of who is traveling.

### `AgentTrace.jsx`
- **What it does:** Shows the "thinking" steps of the AI agent (e.g., "Searching flights...", "Checking seats...").
- **Input (IP):** The trace log from the backend.
- **Output (OP):** A collapsible debug view showing what the AI did behind the scenes.