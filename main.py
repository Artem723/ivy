'''
VCS entry point.
'''
import os

def esc(code):
    return f'\033[{code}m'

def run(video_file_path):
    '''
    Initialize counter class and run counting loop.
    '''

    import ast

    import sys
    import time
    from util.orientation import Orientation
    import cv2

    from util.image import take_screenshot
    from util.logger import get_logger
    from util.debugger import mouse_callback
    from VehicleCounter import VehicleCounter

    logger = get_logger(video_file_path)
    print("CV2: ", cv2)
    # capture traffic scene video
    is_cam = ast.literal_eval(os.getenv('IS_CAM'))
    # video_file = int(os.getenv('VIDEO')) if is_cam else os.getenv('VIDEO')
    cap = cv2.VideoCapture(video_file_path)
    if not cap.isOpened():
        logger.error('Error capturing video. Invalid source.', extra={
            'meta': {'label': 'VIDEO_CAPTURE', 'source': video_file_path},
        })
        sys.exit(0)
    ret, frame = cap.read()
    f_height, f_width, _ = frame.shape

    detection_interval = int(os.getenv('DI'))
    mcdf = int(os.getenv('MCDF'))
    mctf = int(os.getenv('MCTF'))
    detector = os.getenv('DETECTOR')
    tracker = os.getenv('TRACKER')
    orientation_param = int(os.getenv('ORIENTATION'))
    lines_orientation = None
    if orientation_param == 1:
        lines_orientation = Orientation.VERTICAL
    else:
        lines_orientation = Orientation.HORIZONTAL
    # create detection region of interest polygon
    use_droi = ast.literal_eval(os.getenv('USE_DROI'))
    distance_between_speed_labels = int(os.getenv('DISTANCE_BETWEEN_SPEED_LABELS'))
    droi = ast.literal_eval(os.getenv('DROI')) \
            if use_droi \
            else [(0, 0), (f_width, 0), (f_width, f_height), (0, f_height)]
    show_droi = ast.literal_eval(os.getenv('SHOW_DROI'))
    # counting_lines = ast.literal_eval(os.getenv('COUNTING_LINES'))

    examining_lines = ast.literal_eval(os.getenv('EXAMINING_LINES'))
    counting_lines = None
    if lines_orientation == Orientation.VERTICAL:

        counting_lines = [{'label': l['label'], 'line': [l['start'], (l['start'][0], l['start'][1] + l['length'])]} for l in examining_lines]
    else:
        counting_lines = [{'label': l['label'], 'line': [l['start'], (l['start'][0] + l['length'], l['start'][1])]} for l in examining_lines]
    vehicle_counter = VehicleCounter(frame, detector, tracker, droi, show_droi, mcdf,
                                     mctf, detection_interval, counting_lines, 30, distance_between_speed_labels, lines_orientation, video_file_path) # 30 fps

    record = ast.literal_eval(os.getenv('RECORD'))
    headless = ast.literal_eval(os.getenv('HEADLESS'))

    if record:
        # initialize video object to record counting
        output_video = cv2.VideoWriter(os.getenv('OUTPUT_VIDEO_PATH'), \
                                        cv2.VideoWriter_fourcc(*'MJPG'), \
                                        30, \
                                        (f_width, f_height))

    logger.info('Processing started.', extra={
        'meta': {
            'label': 'START_PROCESS',
            'counter_config': {
                'di': detection_interval,
                'mcdf': mcdf,
                'mctf': mctf,
                'detector': detector,
                'tracker': tracker,
                'use_droi': use_droi,
                'droi': droi,
                'show_droi': show_droi,
                'counting_lines': counting_lines
            },
        },
    })

    if not headless:
        # capture mouse events in the debug window
        cv2.namedWindow('Debug')
        cv2.setMouseCallback('Debug', mouse_callback, {'frame_width': f_width, 'frame_height': f_height})

    is_paused = False
    output_frame = None

    # main loop
    while is_cam or cap.get(cv2.CAP_PROP_POS_FRAMES) + 1 < cap.get(cv2.CAP_PROP_FRAME_COUNT):
        k = cv2.waitKey(1) & 0xFF
        if k == ord('p'): # pause/play loop if 'p' key is pressed
            is_paused = False if is_paused else True
            logger.info('Loop paused/played.', extra={'meta': {'label': 'PAUSE_PLAY_LOOP', 'is_paused': is_paused}})
        if k == ord('s') and output_frame is not None: # save frame if 's' key is pressed
            take_screenshot(output_frame)
        if k == ord('q'): # end video loop if 'q' key is pressed
            logger.info('Loop stopped.', extra={'meta': {'label': 'STOP_LOOP'}})
            break

        if is_paused:
            time.sleep(0.5)
            continue

        _timer = cv2.getTickCount() # set timer to calculate processing frame rate

        if ret:
            vehicle_counter.count(frame)
            output_frame = vehicle_counter.visualize()

            if record:
                output_video.write(output_frame)

            if not headless:
                debug_window_size = ast.literal_eval(os.getenv('DEBUG_WINDOW_SIZE'))
                resized_frame = cv2.resize(output_frame, debug_window_size)
                cv2.imshow('Debug', resized_frame)

        processing_frame_rate = round(cv2.getTickFrequency() / (cv2.getTickCount() - _timer), 2)
        frames_processed = round(cap.get(cv2.CAP_PROP_POS_FRAMES))
        frames_count = round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        logger.debug('Frame processed.', extra={
            'meta': {
                'label': 'FRAME_PROCESS',
                'frames_processed': frames_processed,
                'frame_rate': processing_frame_rate,
                'frames_left': frames_count - frames_processed,
                'percentage_processed': round((frames_processed / frames_count) * 100, 2),
            },
        })

        ret, frame = cap.read()

    # end capture, close window, close log file and video object if any
    cap.release()
    if not headless:
        cv2.destroyAllWindows()
    if record:
        output_video.release()
    logger.info('Processing ended.', extra={'meta': {'label': 'END_PROCESS'}})
    
    vehicle_counter.log_results()


if __name__ == '__main__':
    from dotenv import load_dotenv
    from util.logger import init_logger
    
    load_dotenv()
    input = os.getenv('INPUT')    

    if os.path.isdir(input):
        files = os.listdir(input)
        for f_name in files:
            ext = (f_name.split('.')).pop()
            if ext == 'mp4':
                path = os.path.join(input, f_name)
                os.environ['PROCESSING_FILE_PATH'] = path
                init_logger(path)
                run(path)
    
    elif os.path.isfile(input):
        init_logger(input)
        os.environ['PROCESSING_FILE_PATH'] = input
        run(input)
    
    else:
        print(esc('31;1;4') + 'ERROR:' + esc(0) + 'unknown INPUT.')

    

