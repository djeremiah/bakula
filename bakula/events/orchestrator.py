# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing,
#   software distributed under the License is distributed on an
#   "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
#   KIND, either express or implied.  See the License for the
#   specific language governing permissions and limitations
#   under the License.
from bakula.events.inboxer import Inboxer
from bakula.docker.dockeragent import DockerAgent
from bakula.models import Registration, resolve_query
import uuid

# This class handles the event handling of the inboxer and, when a threshold is hit,
# it promotes the appropriate files as an inbox or a docker container then fires the
# docker container.
class Orchestrator:
    def __init__(self, inboxer=Inboxer(), docker_agent=None):
         self.inboxer = inboxer
         self.inboxer.on("received", self.__handle_inbox_received_event)
         self.docker_agent = docker_agent
         if self.docker_agent is None:
             self.docker_agent = DockerAgent()

    # Get listing of registered containers filtered by topic
    def __get_registered_containers(self, topic):
        return Registration.select().where(Registration.topic == topic)

    # This event handler is executed every time a file is put into the master inbox
    # The data argument includes a property specify the topic that was appended to
    def __handle_inbox_received_event(self, data):
        # Get a list of all files in the inbox delineated by the topic in the event
        inbox_list = self.inboxer.get_inbox_list(data["topic"])

        # Are there enough items in the inbox to trigger the threshold?
        if len(inbox_list) >= 1: # This is just a temporary threshold
            # Promote all files in the inbox, delineated by topic, to a directory for
            # a container to mount; returns a list of created inboxes
            container_infos = self.__get_registered_containers(data["topic"])

            if container_infos is None:
                print "Container for topic not found; doing nothing..."
                return None

            container_inboxes = self.inboxer.promote_to_container_inbox(data["topic"], str(uuid.uuid4()))

            if container_inboxes is None or len(container_inboxes) == 0:
                print "There are no container inboxes available for the event run; did something weird happen?"
                return None

            for container_inbox in container_inboxes:
                for container_info in container_infos:
                    # container_inbox is the path inboxer promoted to be mounted in the docker container
                    # container_info is the result from the database that specifies the container name to execute
                    image_name = container_info.container
                    self.docker_agent.pull(image_name)
                    self.docker_agent.start_container(host_inbox=container_inbox, image_name=image_name)
