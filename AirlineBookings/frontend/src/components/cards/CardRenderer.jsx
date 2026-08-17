import FlightOptionsCard from "./FlightOptionsCard";
import HoldCard from "./HoldCard";
import PassengerListCard from "./PassengerListCard";
import SeatMapCard from "./SeatMapCard";
import ReviewCard from "./ReviewCard";
import BookingConfirmationCard from "./BookingConfirmationCard";
import SingleBookingConfirmationCard from "./SingleBookingConfirmationCard";
import BookingCancelledCard from "./BookingCancelledCard";

export default function CardRenderer({ card, passengerCount, onPickFlight, onSelectSeat }) {
  switch (card.type) {
    case "flight_options":
      return <FlightOptionsCard data={card.data} onPick={onPickFlight} />;
    case "hold":
      return <HoldCard data={card.data} />;
    case "passenger_list":
      return <PassengerListCard data={card.data} />;
    case "seatmap":
      return <SeatMapCard data={card.data} passengerCount={passengerCount} onSelectSeat={onSelectSeat} />;
    case "review":
      return <ReviewCard data={card.data} />;
    case "booking_confirmation":
      return <BookingConfirmationCard data={card.data} />;
    case "single_booking_confirmation":
      return <SingleBookingConfirmationCard data={card.data} />;
    case "booking_cancelled":
      return <BookingCancelledCard data={card.data} />;
    default:
      return null;
  }
}
