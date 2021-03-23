from util.orientation import Orientation
import cv2
from tracker import add_new_blobs, remove_duplicates
from collections import OrderedDict
from detectors.detector import get_bounding_boxes
import time
from util.detection_roi import get_roi_frame, draw_roi
from util.logger import get_logger
from counter import has_crossed_counting_line
# TODO: implement speed estimation in the both directions
#       - use Right and LEft bars
#       - use one BAR for counting
FPS = 30
logger = get_logger()


class VehicleCounter():

    def __init__(self, initial_frame, detector, tracker, droi, show_droi, mcdf, mctf, di, counting_lines, fps, distance_between_speed_labels):
        self.frame = initial_frame  # current frame of video
        self.detector = detector
        self.tracker = tracker
        self.droi = droi  # detection region of interest
        self.show_droi = show_droi
        self.mcdf = mcdf  # maximum consecutive detection failures
        self.mctf = mctf  # maximum consecutive tracking failures
        self.di = di  # detection interval
        self.counting_lines = counting_lines

        self.blobs = OrderedDict()
        self.f_height, self.f_width, _ = self.frame.shape
        self.frame_count = 0  # number of frames since last detection
        # counts of vehicles by type for each counting line
        self.counts_by_type_per_line = {
            counting_line['label']: {} for counting_line in counting_lines}

        # speed estimation props
        self.fps = fps if fps is not None else 30
        self.distance_between_speed_labels = distance_between_speed_labels if distance_between_speed_labels is not None else 10  # in meters
        self.moving_orientation = Orientation.HORIZONTAL
        self.sum_speed = 0
        self.times_speed_counted = 0
        self.pxs_lenght_btw_labels = 0
        speed_labels = [ el for el in counting_lines if el['label'][-6:] == "_SPEED" ]

        if not speed_labels:
            if self.moving_orientation == Orientation.HORIZONTAL:
                self.pxs_lenght_btw_labels = abs(speed_labels[0]['line'][0][0] - speed_labels[1]['line'][0][0])
            elif self.moving_orientation == Orientation.VERTICAL:
                self.pxs_lenght_btw_labels = abs(speed_labels[0]['line'][0][1] - speed_labels[1]['line'][0][1])


        # create blobs from initial frame
        droi_frame = get_roi_frame(self.frame, self.droi)
        _bounding_boxes, _classes, _confidences = get_bounding_boxes(
            droi_frame, self.detector)
        self.blobs = add_new_blobs(
            _bounding_boxes, _classes, _confidences, self.blobs, self.frame, self.tracker, self.mcdf)

    def get_blobs(self):
        return self.blobs

    def count(self, frame):
        self.frame = frame

        for _id, blob in list(self.blobs.items()):
            # update trackers
            success, box = blob.tracker.update(self.frame)
            if success:
                blob.num_consecutive_tracking_failures = 0
                blob.update(box)
                logger.debug('Vehicle tracker updated.', extra={
                    'meta': {
                        'label': 'TRACKER_UPDATE',
                        'vehicle_id': _id,
                        'bounding_box': blob.bounding_box,
                        'centroid': blob.centroid,
                    },
                })
            else:
                blob.num_consecutive_tracking_failures += 1

            # count vehicle if it has crossed a counting line
            for counting_line in self.counting_lines:
                label = counting_line['label']
                # if label == "A":
                #     continue
                speed_km_h = -1
                if has_crossed_counting_line(blob.bounding_box, counting_line['line']) and \
                        label not in blob.lines_crossed:
                    if blob.type in self.counts_by_type_per_line[label]:
                        self.counts_by_type_per_line[label][blob.type] += 1
                    else:
                        self.counts_by_type_per_line[label][blob.type] = 1

                    blob.lines_crossed.append(label)
                    if label[-6:] == "_SPEED":
                        if not blob.is_speed_being_estimated:
                            blob.is_speed_being_estimated = True
                            blob.offset_pxs = self.get_offset(
                                blob, counting_line)
                            logger.debug('SPEED ESTIMATION STARTED', extra={
                                'meta': {
                                    'label': "SPEED ESTIMATION",
                                    'label_name': label,
                                    'vehicle_id': _id,
                                    'offset': blob.offset_pxs,
                                }
                            })
                        else:
                            blob.is_speed_being_estimated = False
                            speed_km_h = self.estimate_speed(blob)

                    if label == "C":
                        logger.info('Vehicle counted.', extra={
                            'meta': {
                                'label': 'VEHICLE_COUNT',
                                'id': _id,
                                'type': blob.type,
                                'counting_line': label,
                                'position_first_detected': blob.position_first_detected,
                                'position_counted': blob.centroid,
                                'counted_at': time.time(),
                                'counts_by_type_per_line': self.counts_by_type_per_line,
                                'estimated_speed': (speed_km_h if speed_km_h != -1 else 'N/A'),
                                'FPS': self.fps,
                                'average_estimated_speed': (float(self.sum_speed) / self.times_speed_counted) if self.times_speed_counted != 0 else 'N/A'
                            },
                        })
            if blob.is_speed_being_estimated:
                blob.time_inside_speedmarks += 1

            if blob.num_consecutive_tracking_failures >= self.mctf:
                # delete untracked blobs
                del self.blobs[_id]

        if bool(self.frame_count % self.di):
            # rerun detection
            droi_frame = get_roi_frame(self.frame, self.droi)
            _bounding_boxes, _classes, _confidences = get_bounding_boxes(
                droi_frame, self.detector)
            self.blobs = add_new_blobs(
                _bounding_boxes, _classes, _confidences, self.blobs, self.frame, self.tracker, self.mcdf)
            self.blobs = remove_duplicates(self.blobs)

        self.frame_count += 1

    def visualize(self):
        frame = self.frame
        font = cv2.FONT_HERSHEY_DUPLEX
        line_type = cv2.LINE_AA

        # draw and label blob bounding boxes
        for _id, blob in self.blobs.items():
            (x, y, w, h) = [int(v) for v in blob.bounding_box]
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
            vehicle_label = 'I: ' + _id[:8] \
                            if blob.type is None \
                            else 'I: {0}, T: {1} ({2})'.format(_id[:8], blob.type, str(blob.type_confidence)[:4])
            cv2.putText(frame, vehicle_label, (x, y - 5),
                        font, 1, (255, 0, 0), 2, line_type)

        # draw counting lines
        for counting_line in self.counting_lines:
            cv2.line(frame, counting_line['line'][0],
                     counting_line['line'][1], (255, 0, 0), 3)
            cl_label_origin = (
                counting_line['line'][0][0], counting_line['line'][0][1] + 35)
            cv2.putText(
                frame, counting_line['label'], cl_label_origin, font, 1, (255, 0, 0), 2, line_type)

        # show detection roi
        if self.show_droi:
            frame = draw_roi(frame, self.droi)

        return frame

    def estimate_speed(self, blob):

        time_hours = (blob.time_inside_speedmarks / self.fps) / 3600
        distance = self.get_distance(blob.offset_pxs)

        if time_hours == 0 or distance == 0:
            return -1


        speed_km_h = (distance / 1000) / time_hours
        self.sum_speed += speed_km_h
        self.times_speed_counted += 1

        return speed_km_h

    def get_distance(self, offset):

        ratio = offset / self.pxs_lenght_btw_labels
        if ratio > 1:
            return 0

        return self.distance_between_speed_labels * ratio


    def get_offset(self, blob, counting_line):
        """"Returns an offset in pixels of the blob crossing counting_line"""
        label_prefix = counting_line['name'][0]
        coord_label = 0
        coord_blob = 0

        offset = 0

        if label_prefix != "R" or label_prefix != "L":
            logger.error('ERROR', extra={
                'meta': {
                    'label': 'ERROR',
                    'message': "The speed prefix should be 'L' or 'R' but found: '" + label_prefix + "'"
                },
            })
        if self.moving_orientation == Orientation.HORIZONTAL:
            coord_label = counting_line["line"][0][0]  # take X
            if label_prefix == "L":
                coord_blob = blob.bounding_box[0] + blob.bounding_box[2]
                offset = abs(coord_blob - coord_label)
            elif label_prefix == "R":
                coord_blob = blob.bounding_box[0]
                offset = abs(coord_blob - coord_label)
        else:
            coord_label = counting_line["line"][0][1]  # take Y
            coord_blob = blob.bounding_box[1]
            if label_prefix == "L":
                coord_blob = blob.bounding_box[1]
                offset = abs(coord_blob - coord_label)
            elif label_prefix == "R":
                coord_blob = blob.bounding_box[1] + blob.bounding_box[3]
                offset = abs(coord_blob - coord_label)

        return offset
